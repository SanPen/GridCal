from __future__ import annotations

import gc
import sys

import pytest
from PySide6 import QtWidgets, QtCore, QtGui
import VeraGridEngine.api as gce
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.enumerations import BlockSymbolKind

from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import (
    BlockStructuralEditRequest,
    BlockSymbolDraftRow,
    DynamicBlockPropertiesDialog,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.add_symbol_dialog import AddSymbolSelection
import VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor as dynamic_block_editor
import VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_graphics as graph
import VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_models as dialog_models
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import (
    create_default_template_builder,
    initialize_template_builder_from_block,
)
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry, build_dynamic_editor_entry
from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorTab
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, find_connections
from VeraGridEngine.Utils.Symbolic.dynamic_connection_intent import (DynamicConnectionIntent,
                                                                     DynamicConnectionIntentDirection,
                                                                     DynamicConnectionIntentOrigin)
from VeraGridEngine.Utils.Symbolic.templates_common_functions import attach_emt_model_to_buses
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.enumerations import DynamicSimulationMode, VarPowerFlowReferenceType, BlockType
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_mask
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp

pytestmark = pytest.mark.filterwarnings("error")


class _BusStub:
    __slots__ = ("name", "is_dc", "emt_model", "_pending_emt_devices")

    def __init__(self, name: str, is_dc: bool, emt_model: Block) -> None:
        """Create a minimal bus object for EMT connection tests.

        :param name: Bus name exposed to connection diagnostics.
        :param is_dc: Whether the stub represents a DC bus.
        :param emt_model: Symbolic EMT bus model exposed by the stub.
        """
        self.name = name
        self.is_dc = is_dc
        self.emt_model = emt_model
        self._pending_emt_devices: list[object] = list()


    def get_pending_emt_devices(self) -> list[object]:
        """
        Return the pending EMT device list.

        :return: Pending device list copy.
        """
        return list(self._pending_emt_devices)

    def remove_pending_emt_device(self, device: object) -> None:
        """
        Remove one pending EMT device from the stub bus.

        :param device: Pending device to remove.
        :return: None.
        """
        self._pending_emt_devices = [pending for pending in self._pending_emt_devices if pending is not device]


def _get_app() -> QtWidgets.QApplication:
    """
    Return the shared Qt application used by GUI tests.

    :return: Existing or newly created Qt application.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return app


def _make_var(name: str, reference: VarPowerFlowReferenceType) -> Var:
    """
    Build one symbolic variable with the requested power-flow reference.

    :param name: Variable name.
    :param reference: Power-flow reference tag.
    :return: Symbolic variable.
    """
    return Var(name=name, reference=reference)


def _make_ac_bus(name: str,
                 *,
                 include_neutral: bool = False,
                 include_a: bool = True,
                 include_b: bool = True,
                 include_c: bool = True) -> _BusStub:
    """
    Build one AC bus stub with only the requested phase voltages.

    :param name: Bus name.
    :param include_neutral: Whether to expose the neutral voltage.
    :param include_a: Whether to expose phase A voltage.
    :param include_b: Whether to expose phase B voltage.
    :param include_c: Whether to expose phase C voltage.
    :return: AC bus stub.
    """
    mapping: dict[VarPowerFlowReferenceType, Var] = dict()

    # Build exactly the phase-voltage mapping required by the test case so the
    # editor must derive its connection ports from the bus mask and nothing else.
    if include_neutral:
        mapping[VarPowerFlowReferenceType.v_N] = _make_var(f"v_N_{name}", VarPowerFlowReferenceType.v_N)
    else:
        pass
    if include_a:
        mapping[VarPowerFlowReferenceType.v_A] = _make_var(f"v_A_{name}", VarPowerFlowReferenceType.v_A)
    else:
        pass
    if include_b:
        mapping[VarPowerFlowReferenceType.v_B] = _make_var(f"v_B_{name}", VarPowerFlowReferenceType.v_B)
    else:
        pass
    if include_c:
        mapping[VarPowerFlowReferenceType.v_C] = _make_var(f"v_C_{name}", VarPowerFlowReferenceType.v_C)
    else:
        pass

    return _BusStub(
        name=name,
        is_dc=False,
        emt_model=Block(external_mapping=mapping),
    )


def _make_template(mapping_refs: list[VarPowerFlowReferenceType]) -> EmtModelTemplate:
    """
    Build one minimal EMT template exposing the requested references.

    :param mapping_refs: References to include in the template mapping.
    :return: EMT template.
    """
    template = EmtModelTemplate(name="stub_template")
    template.block = Block(external_mapping={
        reference: _make_var(f"templ_{reference.value}", reference)
        for reference in mapping_refs
    })
    return template


def _dispose_editor(editor: DynamicBlockEditorGUI) -> None:
    """
    Dispose one editor window using the same teardown path as production tabs.

    :param editor: Editor instance to release.
    :return: None.
    """
    app: QtWidgets.QApplication = _get_app()

    # Release the editor-owned models and graphics objects before detaching the
    # top-level widget, matching the ordering used by production editor tabs.
    editor.prepare_to_delete()
    editor.close()
    editor.setParent(None)
    editor.deleteLater()

    # Complete every deferred Qt deletion while the application and the test's
    # Python wrappers are still alive. This prevents a later test allocation
    # from triggering garbage collection over a half-destroyed QObject tree.
    QtCore.QCoreApplication.sendPostedEvents(
        None,
        QtCore.QEvent.Type.DeferredDelete,
    )
    app.processEvents()
    gc.collect()


def _build_phase_bus_block(name: str,
                           mask: list[bool],
                           is_dc: bool = False) -> Block:
    """
    Build one EMT bus block exposing exactly the requested topology mask.

    :param name: Bus label used in variable names.
    :param mask: AC mask ordered as ``[N, A, B, C]``.
    :param is_dc: Whether the bus is DC.
    :return: EMT bus block.
    """
    mapping: dict[VarPowerFlowReferenceType, Var | None] = dict()
    algebraic_vars: list[Var] = list()

    if is_dc:
        vdc: Var = _make_var(f"Vdc_{name}", VarPowerFlowReferenceType.Vdc)
        mapping[VarPowerFlowReferenceType.Vdc] = vdc
        mapping[VarPowerFlowReferenceType.v_N] = None
        mapping[VarPowerFlowReferenceType.v_A] = None
        mapping[VarPowerFlowReferenceType.v_B] = None
        mapping[VarPowerFlowReferenceType.v_C] = None
        algebraic_vars.append(vdc)
    else:
        refs: list[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ])
        ref_index: int
        reference: VarPowerFlowReferenceType
        for ref_index, reference in enumerate(refs):
            if mask[ref_index]:
                variable = _make_var(f"{reference.value}_{name}", reference)
                mapping[reference] = variable
                algebraic_vars.append(variable)
            else:
                mapping[reference] = None
        mapping[VarPowerFlowReferenceType.Vdc] = None

    return Block(algebraic_vars=algebraic_vars,
                 out_vars=list(algebraic_vars),
                 external_mapping=mapping)


def _build_line_with_phases(circuit: MultiCircuit,
                            bus_from: object,
                            bus_to: object,
                            active_phases: list[int]) -> Line:
    """
    Build one static line whose template exposes the requested phases.

    :param circuit: Owning circuit.
    :param bus_from: From bus.
    :param bus_to: To bus.
    :param active_phases: Active phase numbers using the existing template API.
    :return: Configured line.
    """
    import numpy as np
    import VeraGridEngine.api as vge

    z = np.eye(len(active_phases), dtype=complex) * (0.3 + 1j)
    y = np.eye(len(active_phases), dtype=complex) * (1j * 1e-6)
    template = vge.create_known_abc_overhead_template(name=f"templ_{len(active_phases)}_{'_'.join(str(value) for value in active_phases)}",
                                                      z_nabc=z,
                                                      ysh_nabc=y,
                                                      phases=np.array(active_phases),
                                                      Vnom=10.0)
    circuit.add_overhead_line(template)
    line = vge.Line(bus_from=bus_from, bus_to=bus_to)
    line.apply_template(template, circuit.Sbase, circuit.fBase, Logger())
    circuit.add_line(obj=line)
    return line


def _build_root_wrapper(var: Var, is_input: bool, uid: int) -> Block:
    """
    Build one protected-root wrapper block for one interface variable.

    :param var: Wrapped authoritative or legacy root var.
    :param is_input: Whether this is one input wrapper.
    :param uid: Wrapper UID.
    :return: Wrapper block.
    """
    if is_input:
        return Block(uid=uid, name=var.name, out_vars=list([var]))
    else:
        return Block(uid=uid, name=var.name, in_vars=list([var]))


def _add_diagram_wrapper_node(block: Block, x: float, y: float, diagram_tpe: str, root: Block) -> None:
    """
    Add one wrapper node to the persisted diagram.

    :param block: Wrapper block to persist.
    :param x: Diagram x coordinate.
    :param y: Diagram y coordinate.
    :param diagram_tpe: Node type string.
    :param root: Root block owning the diagram.
    :return: None.
    """
    root.diagram.add_node(name=block.name,
                          x=x,
                          y=y,
                          tpe=diagram_tpe,
                          device_uid=block.uid)


class _DirtySpy(QtCore.QObject):
    __slots__ = ("events",)

    def __init__(self) -> None:
        """
        Initialize one dirty-state signal collector.

        :return: None.
        """
        super().__init__()
        self.events: list[bool] = list()

    def record(self, value: bool) -> None:
        """
        Record one dirty-state emission.

        :param value: Dirty-state value.
        :return: None.
        """
        self.events.append(value)


def _make_phase_transition_circuit(initial_phases: list[int],
                                   final_phases: list[int]) -> tuple[MultiCircuit, Load, object, list[int]]:
    """
    Build one single-bus load circuit plus one auxiliary branch to drive the bus mask.

    :param initial_phases: Initial active phase numbers.
    :param final_phases: Final active phase numbers.
    :return: Circuit, load, remote bus and final phase list.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    _build_line_with_phases(circuit=circuit,
                            bus_from=bus,
                            bus_to=remote_bus,
                            active_phases=initial_phases)
    return circuit, load, remote_bus, list(final_phases)


def _apply_bus_phase_transition(circuit: MultiCircuit,
                                bus: object,
                                remote_bus: object,
                                final_phases: list[int]) -> None:
    """
    Change one line template to the final requested phase set.

    :param circuit: Owning circuit.
    :param bus: Local bus.
    :param remote_bus: Remote auxiliary bus.
    :param final_phases: Final phase numbers.
    :return: None.
    """
    import numpy as np
    import VeraGridEngine.api as vge

    z = np.eye(len(final_phases), dtype=complex) * (0.3 + 1j)
    y = np.eye(len(final_phases), dtype=complex) * (1j * 1e-6)
    template = vge.create_known_abc_overhead_template(name=f"transition_{'_'.join(str(value) for value in final_phases)}",
                                                      z_nabc=z,
                                                      ysh_nabc=y,
                                                      phases=np.array(final_phases),
                                                      Vnom=10.0)
    line = circuit.lines[0]
    line.apply_template(template, 100.0, 50.0, Logger())


def _apply_line_phase_transition(line: object,
                                 final_phases: list[int]) -> None:
    """
    Change one specific line template to the final requested phase set.

    :param line: Line whose static topology must change.
    :param final_phases: Final phase numbers.
    :return: None.
    """
    import numpy as np
    import VeraGridEngine.api as vge

    z = np.eye(len(final_phases), dtype=complex) * (0.3 + 1j)
    y = np.eye(len(final_phases), dtype=complex) * (1j * 1e-6)
    template = vge.create_known_abc_overhead_template(name=f"transition_{'_'.join(str(value) for value in final_phases)}",
                                                      z_nabc=z,
                                                      ysh_nabc=y,
                                                      phases=np.array(final_phases),
                                                      Vnom=10.0)
    line.apply_template(template, 100.0, 50.0, Logger())


def _collect_root_refs(block: Block) -> tuple[set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType]]:
    """
    Collect root input and output references.

    :param block: Root block to inspect.
    :return: ``(input_refs, output_refs)``.
    """
    return set(var.ref for var in block.in_vars if var.ref is not None), set(var.ref for var in block.out_vars if var.ref is not None)


def _collect_wrapper_refs(block: Block) -> tuple[set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType]]:
    """Collect the phase references carried by grouped root measurements.

    :param block: Root block containing measurement children.
    :return: Input and output reference sets.
    """
    input_refs: set[VarPowerFlowReferenceType] = set()
    output_refs: set[VarPowerFlowReferenceType] = set()
    child: Block
    variable: Var
    for child in block.children:
        if child.name == BlockType.INPUT_CONN.name:
            for variable in child.out_vars:
                if variable.ref is not None:
                    input_refs.add(variable.ref)
                else:
                    pass
        elif child.name == BlockType.OUTPUT_CONN.name:
            for variable in child.in_vars:
                if variable.ref is not None:
                    output_refs.add(variable.ref)
                else:
                    pass
        else:
            pass
    return input_refs, output_refs


def _build_connected_injection_editor(active_phases: list[int]) -> tuple[DynamicBlockEditorGUI, Load, MultiCircuit, object]:
    """
    Build one root EMT injection editor with real internal Gain blocks per phase.

    :param active_phases: Canonical topology phases.
    :return: Editor, load, circuit and remote bus.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=active_phases)
    load.emt_model = Block()
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=load.emt_model,
                                   root_block=load.emt_model,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    editor.show()
    _get_app().processEvents()
    return editor, load, circuit, remote_bus


def _build_template_backed_generator_editor(active_phases: list[int]) -> tuple[DynamicBlockEditorGUI, Generator, MultiCircuit, object]:
    """
    Build one real generator root EMT editor backed by one applied EMT template.

    :param active_phases: Canonical topology phases.
    :return: Editor, generator, circuit and remote bus.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    generator = gce.Generator(name="Gen 1")
    circuit.add_generator(bus=bus, api_obj=generator)
    line = _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=active_phases)

    template: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(circuit.var_factory)
    generator.emt_template = template
    generator.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)
    line.emt_model = Block(in_vars=list([_make_var("vf_A", VarPowerFlowReferenceType.vf_A)]),
                           out_vars=list([_make_var("if_A", VarPowerFlowReferenceType.if_A)]),
                           external_mapping=dict())

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=generator.emt_model,
                                   root_block=generator.emt_model,
                                   api_object=generator,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    return editor, generator, circuit, remote_bus


def _build_complete_template_generator_editor() -> DynamicBlockEditorGUI:
    """
    Build a generator editor with the production composite EMT template.

    :return: Initialized editor.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus: gce.Bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    generator: Generator = gce.Generator(name="Gen 1")
    circuit.add_generator(bus=bus, api_obj=generator)
    template: EmtModelTemplate = get_complete_generator_template_emt(vf=circuit.var_factory)
    generator.emt_template = template
    generator.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=generator.emt_model,
                                   root_block=generator.emt_model,
                                   api_object=generator,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    return editor


def _show_editor_with_workspace_sized_viewport(editor: DynamicBlockEditorGUI) -> None:
    """
    Show one editor at the representative workspace size from the GUI.

    :param editor: Editor whose deferred initial fit must run.
    :return: None.
    """
    editor.resize(1098, 665)
    editor.show()
    _get_app().processEvents()
    _get_app().processEvents()


def _collect_visible_editor_block_rect(editor: DynamicBlockEditorGUI) -> QtCore.QRectF:
    """
    Collect the scene bounds of every top-level visible editor block.

    :param editor: Editor scene to inspect.
    :return: Unified scene rectangle for all visible blocks.
    """
    target_rect: QtCore.QRectF = QtCore.QRectF()
    item: object
    item_rect: QtCore.QRectF

    for item in editor.scene.items():
        if isinstance(item, (
                graph.BlockItem,
                graph.MeasurementsItem,
                graph.GenericBlockItem,
                graph.RoundBaseArithmeticOpItem,
                graph.RectBaseArithmeticOpItem,
                graph.UnOpItem,
                graph.PairedItem,
        )):
            item_rect = item.sceneBoundingRect()
            if target_rect.isNull():
                target_rect = item_rect
            else:
                target_rect = target_rect.united(item_rect)
        else:
            pass

    return target_rect


def _assert_all_editor_blocks_are_inside_viewport(editor: DynamicBlockEditorGUI) -> None:
    """
    Assert every top-level block is visible inside the current canvas viewport.

    :param editor: Editor whose view transform must be checked.
    :return: None.
    """
    target_rect: QtCore.QRectF = _collect_visible_editor_block_rect(editor=editor)
    mapped_rect: QtCore.QRect = editor.view.mapFromScene(target_rect).boundingRect()
    viewport_rect: QtCore.QRect = editor.view.viewport().rect().adjusted(-1, -1, 1, 1)

    assert target_rect.isNull() is False
    assert viewport_rect.contains(mapped_rect)


def _find_wrapper_item(editor: DynamicBlockEditorGUI,
                       reference: VarPowerFlowReferenceType,
                       is_input: bool) -> object:
    """
    Find one root-interface item containing the requested interface reference.

    :param editor: Editor under test.
    :param reference: Interface reference.
    :param is_input: Whether to look for one input wrapper.
    :return: Matching wrapper item.
    """
    scene_item: object

    for scene_item in editor.scene.items():
        if isinstance(scene_item, graph.ProtectedConnectionBlockItem):
            interface_var = scene_item.get_interface_var()
            if interface_var is not None and interface_var.ref == reference:
                if is_input and len(scene_item.outputs) == 1:
                    return scene_item
                elif not is_input and len(scene_item.inputs) == 1:
                    return scene_item
                else:
                    pass
            else:
                pass
        elif isinstance(scene_item, graph.MeasurementsItem):
            assert scene_item.subsys is not None
            assert editor.get_scene_item_by_block_uid(scene_item.subsys.uid) is scene_item
            interface_ports: list[graph.PortItem]
            if is_input:
                interface_ports = scene_item.outputs
            else:
                interface_ports = scene_item.inputs

            interface_port: graph.PortItem
            for interface_port in interface_ports:
                if interface_port.base_var is not None and interface_port.base_var.ref == reference:
                    return scene_item
                else:
                    pass
        else:
            pass

    raise AssertionError(f"Wrapper not found for {reference}")


def _find_wrapper_port(editor: DynamicBlockEditorGUI,
                       reference: VarPowerFlowReferenceType,
                       is_input: bool) -> graph.PortItem:
    """Find one root-interface port by its semantic reference.

    :param editor: Editor under test.
    :param reference: Interface reference carried by the required port.
    :param is_input: Whether the root-interface item supplies an input to the diagram.
    :return: Matching graphical port.
    """
    wrapper_item: object = _find_wrapper_item(
        editor=editor,
        reference=reference,
        is_input=is_input,
    )
    return _find_item_port_by_reference(
        item=wrapper_item,
        reference=reference,
        is_input=not is_input,
    )


def _find_item_port_by_reference(
        item: object,
        reference: VarPowerFlowReferenceType,
        is_input: bool,
) -> graph.PortItem:
    """
    Find one graphical block port by its model-side semantic reference.

    :param item: Graphics block item exposing input and output lists.
    :param reference: Required model-side reference.
    :param is_input: Whether to inspect input ports.
    :return: Matching graphical port.
    """
    ports: list[graph.PortItem] = item.inputs if is_input else item.outputs
    port: graph.PortItem

    for port in ports:
        if port.base_var is not None and port.base_var.ref == reference:
            return port
        else:
            pass

    raise AssertionError(f"Port not found for {reference}")


def _add_gain_item(editor: DynamicBlockEditorGUI, x_pos: float, y_pos: float) -> object:
    """
    Add one real Gain block through the production creation path.

    :param editor: Editor under test.
    :param x_pos: Diagram x coordinate.
    :param y_pos: Diagram y coordinate.
    :return: Gain item.
    """
    item = editor.create_block_item_from_blocktype(BlockType.GAIN, x_pos, y_pos)
    assert item is not None
    return item


def _add_thevenin_item(editor: DynamicBlockEditorGUI, x_pos: float, y_pos: float) -> object:
    """
    Add one real EMT Thevenin block through the production creation path.

    :param editor: Editor under test.
    :param x_pos: Diagram x coordinate.
    :param y_pos: Diagram y coordinate.
    :return: Thevenin item.
    """
    item = editor.create_block_item_from_blocktype(BlockType.EMT_THEVENIN, x_pos, y_pos)
    assert item is not None
    return item


def _connect_port_pair(editor: DynamicBlockEditorGUI,
                       source_port: object,
                       target_port: object) -> None:
    """
    Create one real production connection through the scene controller.

    :param editor: Editor under test.
    :param source_port: Source output port.
    :param target_port: Target input port.
    :return: None.
    """
    editor.scene.connect_ports(source_port, target_port)


def _build_connected_gain_phase(editor: DynamicBlockEditorGUI,
                                voltage_reference: VarPowerFlowReferenceType,
                                current_reference: VarPowerFlowReferenceType,
                                x_pos: float,
                                y_pos: float) -> tuple[object, int, int, int]:
    """
    Build one connected per-phase Gain path from root voltage to root current.

    :param editor: Editor under test.
    :param voltage_reference: Root voltage reference.
    :param current_reference: Root current reference.
    :param x_pos: Gain x position.
    :param y_pos: Gain y position.
    :return: Gain item and root/gain connection UIDs.
    """
    input_wrapper = _find_wrapper_item(editor, voltage_reference, True)
    output_wrapper = _find_wrapper_item(editor, current_reference, False)
    gain_item = _add_gain_item(editor, x_pos, y_pos)
    input_port: graph.PortItem = _find_item_port_by_reference(
        item=input_wrapper,
        reference=voltage_reference,
        is_input=False,
    )
    output_port: graph.PortItem = _find_item_port_by_reference(
        item=output_wrapper,
        reference=current_reference,
        is_input=True,
    )

    _connect_port_pair(editor, input_port, gain_item.inputs[0])
    _connect_port_pair(editor, gain_item.outputs[0], output_port)

    assert input_wrapper.subsys is not None
    assert output_wrapper.subsys is not None
    assert input_port.connections is not None
    assert gain_item.outputs[0].connections is not None
    in_connection_uid = input_port.connections[0].con_uid
    out_connection_uid = gain_item.outputs[0].connections[0].con_uid
    return gain_item, input_wrapper.subsys.uid, output_wrapper.subsys.uid, in_connection_uid, out_connection_uid


def test_removing_existing_output_disconnects_its_live_arrow_before_scene_rebuild() -> None:
    """Unchecking Output must remove its wire and VarFactory edge before port mutation."""
    editor: DynamicBlockEditorGUI
    load: Load
    circuit: MultiCircuit
    remote_bus: object
    editor, load, circuit, remote_bus = _build_connected_injection_editor(active_phases=list([1, 2, 3]))
    _unused_load: Load = load
    _unused_circuit: MultiCircuit = circuit
    _unused_remote_bus: object = remote_bus
    dialogue: DynamicBlockPropertiesDialog | None = None
    try:
        gain_data: tuple[object, int, int, int, int] = _build_connected_gain_phase(
            editor=editor,
            voltage_reference=VarPowerFlowReferenceType.v_A,
            current_reference=VarPowerFlowReferenceType.i_A,
            x_pos=260.0,
            y_pos=180.0,
        )
        gain_item_object: object = gain_data[0]
        incoming_connection_uid: int = gain_data[3]
        outgoing_connection_uid: int = gain_data[4]
        assert isinstance(gain_item_object, graph.UnOpItem)
        assert gain_item_object.subsys is not None
        gain_block: Block = gain_item_object.subsys
        exported_variable: Var = gain_block.out_vars[0]
        dialogue = DynamicBlockPropertiesDialog(
            block=gain_block,
            block_type_name=BlockType.GAIN.name,
            var_factory=editor.var_factory,
        )
        dialogue.outputExportChangesRequested.connect(editor.on_output_export_changes_requested)
        dialogue.blockApplied.connect(editor.on_block_properties_applied)

        output_row: int = -1
        row_index: int
        for row_index in range(dialogue._symbol_model.rowCount()):
            candidate_row: BlockSymbolDraftRow | None = dialogue._symbol_model.get_row(row_index)
            if candidate_row is not None and candidate_row.get_variable() is exported_variable:
                output_row = row_index
            else:
                pass
        assert output_row >= 0
        output_index: QtCore.QModelIndex = dialogue._symbol_model.index(output_row, 3)
        assert dialogue._symbol_model.setData(
            output_index,
            QtCore.Qt.CheckState.Unchecked,
            QtCore.Qt.ItemDataRole.CheckStateRole,
        )

        dialogue.apply_changes()

        assert gain_block.out_vars == list()
        assert incoming_connection_uid in editor.diagram.con_data
        assert outgoing_connection_uid not in editor.diagram.con_data
        assert editor._find_var_factory_connection(
            incoming_non_mutable_uid=editor.main_block.out_vars[0].non_mutable_uid,
            substituted_non_mutable_uid=exported_variable.non_mutable_uid,
        ) is None
    finally:
        if dialogue is not None:
            dialogue.close()
        else:
            pass
        _dispose_editor(editor)


def test_adding_input_from_properties_rebuilds_the_visible_block_port() -> None:
    """Applying a staged input must immediately add its graphics-scene port."""
    editor: DynamicBlockEditorGUI
    load: Load
    circuit: MultiCircuit
    remote_bus: object
    editor, load, circuit, remote_bus = _build_connected_injection_editor(
        active_phases=list([1, 2, 3])
    )
    _unused_load: Load = load
    _unused_circuit: MultiCircuit = circuit
    _unused_remote_bus: object = remote_bus
    dialogue: DynamicBlockPropertiesDialog | None = None
    try:
        generic_item: graph.GenericBlockItem | None = editor.create_block_item_from_blocktype(
            BlockType.PI_CURRENT_CONTROLLER,
            260.0,
            180.0,
        )
        assert isinstance(generic_item, graph.GenericBlockItem)
        assert generic_item.subsys is not None
        generic_block: Block = generic_item.subsys
        generic_block_uid: int = generic_block.uid
        initial_input_count: int = len(generic_item.inputs)
        dialogue = DynamicBlockPropertiesDialog(
            block=generic_block,
            block_type_name=BlockType.PI_CURRENT_CONTROLLER.name,
            var_factory=editor.var_factory,
        )
        dialogue.blockApplied.connect(editor.on_block_properties_applied)
        add_selection: AddSymbolSelection = AddSymbolSelection(
            owner=generic_block,
            name="additional_input",
            kind=BlockSymbolKind.INPUT,
            exported=False,
            value=0.0,
            create_derivative=False,
            external_reference=None,
            static_reference=None,
        )
        dialogue._stage_add_symbol_selection(selection=add_selection)

        dialogue.apply_changes()
        dialogue = None

        rebuilt_item: graph.BlockItem | graph.GenericBlockItem | None = (
            editor.get_scene_item_by_block_uid(generic_block_uid)
        )
        assert isinstance(rebuilt_item, graph.GenericBlockItem)
        assert len(rebuilt_item.inputs) == initial_input_count + 1
        assert rebuilt_item.inputs[-1].base_var is generic_block.in_vars[-1]
        assert generic_block.in_vars[-1].name == "additional_input"

        added_variable: Var = generic_block.in_vars[-1]
        dialogue = DynamicBlockPropertiesDialog(
            block=generic_block,
            block_type_name=BlockType.PI_CURRENT_CONTROLLER.name,
            var_factory=editor.var_factory,
        )
        dialogue.blockApplied.connect(editor.on_block_properties_applied)
        added_row: int = -1
        row_index: int
        for row_index in range(dialogue._symbol_model.rowCount()):
            candidate_row: BlockSymbolDraftRow | None = dialogue._symbol_model.get_row(row_index)
            if candidate_row is not None and candidate_row.get_variable() is added_variable:
                added_row = row_index
            else:
                pass
        assert added_row >= 0
        assert dialogue._symbol_model.remove_symbol(added_row)

        dialogue.apply_changes()
        dialogue = None

        restored_item: graph.BlockItem | graph.GenericBlockItem | None = (
            editor.get_scene_item_by_block_uid(generic_block_uid)
        )
        assert isinstance(restored_item, graph.GenericBlockItem)
        assert len(restored_item.inputs) == initial_input_count
        assert added_variable not in generic_block.in_vars
    finally:
        if dialogue is not None:
            dialogue.close()
        else:
            pass
        _dispose_editor(editor)


def test_deleting_generic_input_removes_only_its_direct_nested_wrapper() -> None:
    """Deleting a parent input must remove its direct wrapper and saved wire.

    :return: None.
    """
    editor: DynamicBlockEditorGUI
    load: Load
    circuit: MultiCircuit
    remote_bus: object
    editor, load, circuit, remote_bus = _build_connected_injection_editor(
        active_phases=list([1, 2, 3])
    )
    _unused_load: Load = load
    _unused_circuit: MultiCircuit = circuit
    _unused_remote_bus: object = remote_bus
    dialogue: DynamicBlockPropertiesDialog | None = None
    try:
        generic_item: graph.GenericBlockItem | None = editor.create_block_item_from_blocktype(
            BlockType.GENERIC,
            260.0,
            180.0,
        )
        assert isinstance(generic_item, graph.GenericBlockItem)
        assert generic_item.subsys is not None
        generic_block: Block = generic_item.subsys
        removed_input: Var = generic_block.in_vars[0]
        retained_input: Var = editor.var_factory.add_var("retained_input")
        generic_block.in_vars.append(retained_input)

        removed_wrapper: Block = _build_root_wrapper(removed_input, True, 8101)
        retained_wrapper: Block = _build_root_wrapper(retained_input, True, 8102)
        internal_input: Var = editor.var_factory.add_var("internal_input")
        internal_input_uid: int = internal_input.uid
        internal_block: Block = Block(name="Internal", uid=8103, in_vars=list([internal_input]))

        # A deeper wrapper using the same identity proves that synchronization
        # is deliberately limited to the edited block's immediate children.
        nested_wrapper: Block = _build_root_wrapper(removed_input, True, 8201)
        internal_block.children.append(nested_wrapper)
        _add_diagram_wrapper_node(
            block=nested_wrapper,
            x=15.0,
            y=15.0,
            diagram_tpe=BlockType.INPUT_CONN.name,
            root=internal_block,
        )

        generic_block.children.extend(list([removed_wrapper, retained_wrapper, internal_block]))
        _add_diagram_wrapper_node(
            block=removed_wrapper,
            x=15.0,
            y=100.0,
            diagram_tpe=BlockType.INPUT_CONN.name,
            root=generic_block,
        )
        _add_diagram_wrapper_node(
            block=retained_wrapper,
            x=15.0,
            y=180.0,
            diagram_tpe=BlockType.INPUT_CONN.name,
            root=generic_block,
        )
        generic_block.diagram.add_node(
            name=internal_block.name,
            x=240.0,
            y=100.0,
            tpe=BlockType.GENERIC.name,
            device_uid=internal_block.uid,
        )
        removed_connection_uid: int = 8301
        generic_block.diagram.add_branch(
            connectionitem_uid=removed_connection_uid,
            device_uid_from=removed_wrapper.uid,
            device_uid_to=internal_block.uid,
            port_number_from=0,
            port_number_to=0,
        )
        editor.var_factory.add_connection(internal_input, removed_input)

        dialogue = DynamicBlockPropertiesDialog(
            block=generic_block,
            block_type_name=BlockType.GENERIC.name,
            var_factory=editor.var_factory,
        )
        dialogue.symbolRemovalsRequested.connect(editor.on_symbol_removals_requested)
        dialogue.blockApplied.connect(editor.on_block_properties_applied)

        removed_row_index: int = -1
        row_index: int
        for row_index in range(dialogue._symbol_model.rowCount()):
            candidate_row: BlockSymbolDraftRow | None = dialogue._symbol_model.get_row(row_index)
            if (
                    candidate_row is not None
                    and candidate_row.get_owner() is generic_block
                    and candidate_row.get_variable() is removed_input
            ):
                removed_row_index = row_index
            else:
                pass
        assert removed_row_index >= 0
        assert dialogue._symbol_model.remove_symbol(removed_row_index)

        dialogue.apply_changes()

        direct_child_uids: set[int] = set(child.uid for child in generic_block.children)
        assert removed_input not in generic_block.in_vars
        assert retained_input in generic_block.in_vars
        assert removed_wrapper.uid not in direct_child_uids
        assert retained_wrapper.uid in direct_child_uids
        assert internal_block.uid in direct_child_uids
        assert removed_wrapper.uid not in generic_block.diagram.node_data
        assert retained_wrapper.uid in generic_block.diagram.node_data
        assert removed_connection_uid not in generic_block.diagram.con_data
        assert nested_wrapper in internal_block.children
        assert nested_wrapper.uid in internal_block.diagram.node_data
        assert internal_input.uid == internal_input_uid
        assert internal_input.name == "internal_input"
        assert editor._find_var_factory_connection(
            incoming_non_mutable_uid=removed_input.non_mutable_uid,
            substituted_non_mutable_uid=internal_input.non_mutable_uid,
        ) is None
    finally:
        if dialogue is not None:
            dialogue.close()
        else:
            pass
        _dispose_editor(editor)


def _active_bus_voltage_refs(bus: object) -> tuple[VarPowerFlowReferenceType, ...]:
    """
    Return the active AC bus-shell voltage refs.

    :param bus: Bus under test.
    :return: Ordered voltage refs currently exposed by ``bus.emt_model``.
    """
    refs: list[VarPowerFlowReferenceType] = list()
    reference: VarPowerFlowReferenceType
    for reference in [
        VarPowerFlowReferenceType.v_N,
        VarPowerFlowReferenceType.v_A,
        VarPowerFlowReferenceType.v_B,
        VarPowerFlowReferenceType.v_C,
    ]:
        if bus.emt_model.external_mapping.get(reference, None) is not None:
            refs.append(reference)
        else:
            pass
    return tuple(refs)


def _count_root_refs(block: Block,
                     expected_inputs: set[VarPowerFlowReferenceType],
                     expected_outputs: set[VarPowerFlowReferenceType]) -> None:
    """
    Assert expected root refs exist exactly once.

    :param block: Root block to inspect.
    :param expected_inputs: Expected input refs.
    :param expected_outputs: Expected output refs.
    :return: None.
    """
    input_refs = [var.ref for var in block.in_vars]
    output_refs = [var.ref for var in block.out_vars]
    reference: VarPowerFlowReferenceType

    for reference in expected_inputs:
        assert input_refs.count(reference) == 1

    for reference in expected_outputs:
        assert output_refs.count(reference) == 1


def _assert_scene_wrapper_counts(editor: DynamicBlockEditorGUI,
                                 expected_input_refs: set[VarPowerFlowReferenceType],
                                 expected_output_refs: set[VarPowerFlowReferenceType]) -> None:
    """
    Assert root-interface visibility and reference counts.

    :param editor: Editor under test.
    :param expected_input_refs: Expected visible input wrapper refs.
    :param expected_output_refs: Expected visible output wrapper refs.
    :return: None.
    """
    scene_input_refs: list[VarPowerFlowReferenceType] = list()
    scene_output_refs: list[VarPowerFlowReferenceType] = list()
    item: object

    for item in editor.scene.items():
        if isinstance(item, graph.ProtectedConnectionBlockItem):
            interface_var = item.get_interface_var()
            assert interface_var is not None
            if len(item.outputs) == 1:
                scene_input_refs.append(interface_var.ref)
            elif len(item.inputs) == 1:
                scene_output_refs.append(interface_var.ref)
            else:
                pass
        elif isinstance(item, graph.MeasurementsItem):
            assert item.subsys is not None
            assert editor.get_scene_item_by_block_uid(item.subsys.uid) is item
            output_port: graph.PortItem
            for output_port in item.outputs:
                if output_port.base_var is not None and output_port.base_var.ref is not None:
                    matching_input_refs: list[VarPowerFlowReferenceType] = list()
                    input_reference: VarPowerFlowReferenceType
                    mapped_input_var: Var | None
                    for input_reference in expected_input_refs:
                        mapped_input_var = editor.main_block.external_mapping.get(input_reference, None)
                        if (mapped_input_var is not None
                                and mapped_input_var.non_mutable_uid == output_port.base_var.non_mutable_uid):
                            matching_input_refs.append(input_reference)
                        else:
                            pass
                    if len(matching_input_refs) == 1:
                        scene_input_refs.append(matching_input_refs[0])
                    else:
                        scene_input_refs.append(output_port.base_var.ref)
                else:
                    pass
            input_port: graph.PortItem
            for input_port in item.inputs:
                if input_port.base_var is not None and input_port.base_var.ref is not None:
                    matching_output_refs: list[VarPowerFlowReferenceType] = list()
                    output_reference: VarPowerFlowReferenceType
                    mapped_output_var: Var | None
                    for output_reference in expected_output_refs:
                        mapped_output_var = editor.main_block.external_mapping.get(output_reference, None)
                        if (mapped_output_var is not None
                                and mapped_output_var.non_mutable_uid == input_port.base_var.non_mutable_uid):
                            matching_output_refs.append(output_reference)
                        else:
                            pass
                    if len(matching_output_refs) == 1:
                        scene_output_refs.append(matching_output_refs[0])
                    else:
                        scene_output_refs.append(input_port.base_var.ref)
                else:
                    pass
        else:
            pass

    reference: VarPowerFlowReferenceType
    for reference in expected_input_refs:
        assert scene_input_refs.count(reference) == 1
    for reference in expected_output_refs:
        assert scene_output_refs.count(reference) == 1


def _assert_root_wrapper_layers(editor: DynamicBlockEditorGUI,
                                expected_input_refs: set[VarPowerFlowReferenceType],
                                expected_output_refs: set[VarPowerFlowReferenceType]) -> None:
    """Check root, mapping, grouped measurements and visible ports together.

    :param editor: Root editor under test.
    :param expected_input_refs: Expected root voltage refs.
    :param expected_output_refs: Expected root current refs.
    :return: None.
    """
    _count_root_refs(editor.main_block, expected_input_refs, expected_output_refs)
    assert _collect_wrapper_refs(editor.main_block) == (expected_input_refs, expected_output_refs)
    items: list[graph.MeasurementsItem] = list(item for item in editor.scene.items()
                                              if isinstance(item, graph.MeasurementsItem))
    assert len(items) == 2
    assert editor._emt_measurements_match_root_interface(items)
    assert set(editor.diagram.node_data).issuperset(item.subsys.uid for item in items)
    _assert_scene_wrapper_counts(editor, expected_input_refs, expected_output_refs)
    assert not any(isinstance(item, graph.GenericBlockItem) and item.subsys is editor.main_block
                   for item in editor.scene.items())


def _expected_input_output_refs_for_phases(phases: list[int]) -> tuple[set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType]]:
    """
    Build expected injection root refs for one AC phase-number set.

    :param phases: Active phase numbers.
    :return: Expected input/output refs.
    """
    input_refs: set[VarPowerFlowReferenceType] = set()
    output_refs: set[VarPowerFlowReferenceType] = set()

    if 0 in phases:
        input_refs.add(VarPowerFlowReferenceType.v_N)
        output_refs.add(VarPowerFlowReferenceType.i_N)
    else:
        pass
    if 1 in phases:
        input_refs.add(VarPowerFlowReferenceType.v_A)
        output_refs.add(VarPowerFlowReferenceType.i_A)
    if 2 in phases:
        input_refs.add(VarPowerFlowReferenceType.v_B)
        output_refs.add(VarPowerFlowReferenceType.i_B)
    if 3 in phases:
        input_refs.add(VarPowerFlowReferenceType.v_C)
        output_refs.add(VarPowerFlowReferenceType.i_C)

    return input_refs, output_refs

def test_first_open_root_emt_editor_does_not_render_main_block() -> None:
    """
    Verify a fresh root EMT editor shows only root connection ovals.

    :return: None.
    """
    editor, _load, _circuit, _remote_bus = _build_connected_injection_editor(active_phases=list([1, 2, 3]))
    try:
        generic_root_items = [
            item for item in editor.scene.items()
            if isinstance(item, graph.GenericBlockItem) and item.subsys is editor.main_block
        ]
        non_interface_root_nodes = [
            node for node in editor.diagram.node_data.values()
            if node.device_uid == editor.main_block.uid and node.tpe not in {"INPUT_CONN", "OUTPUT_CONN"}
        ]
        assert len(generic_root_items) == 0
        assert len(non_interface_root_nodes) == 0
        assert editor.has_unapplied_changes is False
    finally:
        _dispose_editor(editor)


@pytest.mark.parametrize(("initial_phases", "final_phases", "fan_out"), (
    ((1, 2, 3), (1, 2), False), ((1, 2, 3), (1, 3), False),
    ((1, 2), (1, 2, 3), False), ((1, 2, 3), (1, 2), True),
))
def test_saved_injection_editor_topology_change_apply_reopen_matrix(initial_phases: tuple[int, ...],
                                                                    final_phases: tuple[int, ...],
                                                                    fan_out: bool) -> None:
    """Preserve user-to-user wires through isolated workspace save and reopen.

    :param initial_phases: Original static topology.
    :param final_phases: Static topology after the first page has closed.
    :param fan_out: Whether the first gain feeds both the root current and the second gain.
    :return: None.
    """
    application: QtWidgets.QApplication = _get_app()
    circuit: MultiCircuit
    load: Load
    remote_bus: object
    final_phase_list: list[int]
    circuit, load, remote_bus, final_phase_list = _make_phase_transition_circuit(
        initial_phases=list(initial_phases), final_phases=list(final_phases))
    entry: DynamicEditorEntry | None = build_dynamic_editor_entry(load, circuit)
    assert entry is not None
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    page: DynamicEditorTab = session.create_page(entry, DynamicSimulationMode.EMT)
    editor: DynamicBlockEditorGUI | None = page.editor
    assert editor is not None
    gain_a_uid: int
    gain_b_uid: int
    internal_connection_uid: int
    try:
        gain_a: graph.UnOpItem = _add_gain_item(editor, 200.0, 80.0)
        gain_b: graph.UnOpItem = _add_gain_item(editor, 360.0, 220.0)
        # Cover ordinary chains and the original current-output fan-out separately.
        # The former RuntimeError guard must not hide restoration failures in either path.
        _connect_port_pair(editor, _find_wrapper_port(editor, VarPowerFlowReferenceType.v_A, True), gain_a.inputs[0])
        if fan_out:
            _connect_port_pair(editor, gain_a.outputs[0], _find_wrapper_port(editor, VarPowerFlowReferenceType.i_A, False))
        else:
            pass
        _connect_port_pair(editor, gain_a.outputs[0], gain_b.inputs[0])
        if not fan_out:
            _connect_port_pair(editor, gain_b.outputs[0], _find_wrapper_port(editor, VarPowerFlowReferenceType.i_A, False))
        else:
            pass
        gain_a_uid = gain_a.subsys.uid
        gain_b_uid = gain_b.subsys.uid
        internal_connection_uids: list[int] = list(uid for uid, record in editor.diagram.con_data.items()
                                                  if record.from_uid == gain_a_uid and record.to_uid == gain_b_uid)
        assert len(internal_connection_uids) == 1
        internal_connection_uid = internal_connection_uids[0]
        editor.persist_changes_only()
        assert not page.has_unapplied_changes
    finally:
        page.prepare_to_delete()
        page.close()
        page.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        application.processEvents()

    _apply_bus_phase_transition(circuit, load.bus, remote_bus, final_phase_list)
    reopened_page: DynamicEditorTab = session.create_page(entry, DynamicSimulationMode.EMT)
    reopened: DynamicBlockEditorGUI | None = reopened_page.editor
    assert reopened is not None
    try:
        expected_inputs, expected_outputs = _expected_input_output_refs_for_phases(final_phase_list)
        _assert_root_wrapper_layers(reopened, expected_inputs, expected_outputs)
        assert gain_a_uid in reopened.diagram.node_data
        assert gain_b_uid in reopened.diagram.node_data
        assert internal_connection_uid in reopened.diagram.con_data
        assert reopened.diagram.con_data[internal_connection_uid].from_uid == gain_a_uid
        assert reopened.diagram.con_data[internal_connection_uid].to_uid == gain_b_uid
        assert reopened.has_unapplied_changes
        reopened.persist_changes_only()
    finally:
        reopened_page.prepare_to_delete()
        reopened_page.close()
        reopened_page.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        application.processEvents()

    final_page: DynamicEditorTab = session.create_page(entry, DynamicSimulationMode.EMT)
    final_editor: DynamicBlockEditorGUI | None = final_page.editor
    assert final_editor is not None
    try:
        _assert_root_wrapper_layers(final_editor, expected_inputs, expected_outputs)
        assert internal_connection_uid in final_editor.diagram.con_data
        assert not final_page.has_unapplied_changes
    finally:
        final_page.prepare_to_delete()
        final_page.close()
        final_page.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        application.processEvents()


def test_manual_exponential_load_partial_connections_survive_apply_and_reopen() -> None:
    """
    Preserve a manually added exponential-load block and its partial root wiring.

    :return: None.
    """
    generator_editor, generator, circuit, load_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3]))
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=load_bus, api_obj=load)
    _dispose_editor(generator_editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=load_bus,
                                final_phases=list([1, 2]))
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    intermediate_generator_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                                          current_block=generator.emt_model,
                                                          root_block=generator.emt_model,
                                                          api_object=generator,
                                                          current_theme="Light",
                                                          circuit=circuit,
                                                          mode=DynamicSimulationMode.EMT,
                                                          templates_list=list(),
                                                          is_root_editor=True,
                                                          modal=False)
    _dispose_editor(intermediate_generator_editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=load_bus,
                                final_phases=list([1, 2, 3]))
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    restored_generator_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                                      current_block=generator.emt_model,
                                                      root_block=generator.emt_model,
                                                      api_object=generator,
                                                      current_theme="Light",
                                                      circuit=circuit,
                                                      mode=DynamicSimulationMode.EMT,
                                                      templates_list=list(),
                                                      is_root_editor=True,
                                                      modal=False)

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=load.emt_model,
                                   root_block=load.emt_model,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    try:
        exponential_load_item = editor.create_item_using_blocktype_wizard(
            blocktype=BlockType.EXP_LOAD_EMT,
            x_pos=260.0,
            y_pos=180.0)
        assert isinstance(exponential_load_item, graph.GenericBlockItem)
        assert len(exponential_load_item.inputs) == 3
        assert len(exponential_load_item.outputs) == 3

        _connect_port_pair(editor=editor,
                           source_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.v_A, True),
                           target_port=exponential_load_item.inputs[0])
        _connect_port_pair(editor=editor,
                           source_port=exponential_load_item.outputs[1],
                           target_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.i_B, False))
        editor.apply_changes()
    finally:
        _dispose_editor(editor)

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    reopened_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                            current_block=load.emt_model,
                                            root_block=load.emt_model,
                                            api_object=load,
                                            current_theme="Light",
                                            circuit=circuit,
                                            mode=DynamicSimulationMode.EMT,
                                            templates_list=list(),
                                            is_root_editor=True,
                                            modal=False)
    try:
        reopened_editor.show()
        _get_app().processEvents()
        internal_items = list(
            scene_item for scene_item in reopened_editor.scene.items()
            if (isinstance(scene_item, graph.GenericBlockItem)
                and scene_item.subsys is not None
                and not dynamic_block_editor.is_root_interface_wrapper_block(
                    block_model=scene_item.subsys,
                    diagram=reopened_editor.diagram,
                ))
        )
        assert len(internal_items) == 1
        assert internal_items[0].subsys.name.startswith("EXP_Load_EMT")

        connection_refs = _collect_graphical_connection_refs(editor=reopened_editor)
        assert (VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_A) in connection_refs
        assert (VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_B) in connection_refs
        assert (VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_B) not in connection_refs
        assert (VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_A) not in connection_refs
    finally:
        _dispose_editor(reopened_editor)
        _dispose_editor(restored_generator_editor)


def test_generated_phase_rebuild_preserves_surviving_port_connections() -> None:
    """A generated ABC-to-AB rebuild must retain the connected A/B identities."""
    generator_editor: DynamicBlockEditorGUI
    generator: Generator
    circuit: MultiCircuit
    load_bus: gce.Bus
    generator_editor, generator, circuit, load_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3])
    )
    load: Load = gce.Load(name="Load structural")
    circuit.add_load(bus=load_bus, api_obj=load)
    _dispose_editor(generator_editor)
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=circuit.var_factory,
        current_block=load.emt_model,
        root_block=load.emt_model,
        api_object=load,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    try:
        exponential_load_item: graph.GenericBlockItem | None = editor.create_item_using_blocktype_wizard(
            blocktype=BlockType.EXP_LOAD_EMT,
            x_pos=260.0,
            y_pos=180.0,
        )
        assert isinstance(exponential_load_item, graph.GenericBlockItem)
        assert exponential_load_item.subsys is not None
        target_block: Block = exponential_load_item.subsys
        old_input_a: Var = target_block.in_vars[0]
        old_output_b: Var = target_block.out_vars[1]
        _connect_port_pair(
            editor=editor,
            source_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.v_A, True),
            target_port=exponential_load_item.inputs[0],
        )
        _connect_port_pair(
            editor=editor,
            source_port=exponential_load_item.outputs[1],
            target_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.i_B, False),
        )

        builder: TemplateDefinition | None = create_default_template_builder(
            var_factory=editor.var_factory,
            block_type=BlockType.EXP_LOAD_EMT,
            item_name=target_block.name,
            api_object=load,
        )
        assert builder is not None
        initialize_template_builder_from_block(builder, target_block, BlockType.EXP_LOAD_EMT)
        phase_c_property: TemplateProp | None = builder.params_dict.get("phC", None)
        assert phase_c_property is not None
        phase_c_property.value = False
        request: BlockStructuralEditRequest = BlockStructuralEditRequest(
            block=target_block,
            block_type=BlockType.EXP_LOAD_EMT,
            builder=builder,
            parameter_values=list(),
        )

        editor.on_structural_rebuild_requested(request)

        assert request.is_successful()
        assert len(target_block.in_vars) == 2
        assert len(target_block.out_vars) == 2
        assert target_block.in_vars[0] is old_input_a
        assert target_block.out_vars[1] is old_output_b
        assert len(editor.diagram.con_data) == 2
    finally:
        _dispose_editor(editor)


def test_workspace_exponential_load_partial_connections_survive_tab_close_and_reopen() -> None:
    """
    Preserve a partially wired exponential load through real workspace tab teardown.

    :return: None.
    """
    app = _get_app()
    generator_editor, generator, circuit, load_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3]))
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=load_bus, api_obj=load)
    _dispose_editor(generator_editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=load_bus,
                                final_phases=list([1, 2]))
    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=load_bus,
                                final_phases=list([1, 2, 3]))

    session = DynamicEditorWorkspaceSession()
    workspace = DynamicEditorWorkspaceWindow(session=session)
    workspace.show()
    generator_page = workspace.open_dynamic_editor_for(
        api_object=generator,
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace)
    assert generator_page is not None

    load_page = workspace.open_dynamic_editor_for(api_object=load,
                                                  circuit=circuit,
                                                  preferred_mode=DynamicSimulationMode.EMT,
                                                  target_workspace=workspace)
    assert load_page is not None
    editor = load_page.editor
    assert editor is not None
    exponential_load_item = editor.create_item_using_blocktype_wizard(
        blocktype=BlockType.EXP_LOAD_EMT,
        x_pos=260.0,
        y_pos=180.0)
    assert isinstance(exponential_load_item, graph.GenericBlockItem)
    _connect_port_pair(editor=editor,
                       source_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.v_A, True),
                       target_port=exponential_load_item.inputs[0])
    _connect_port_pair(editor=editor,
                       source_port=exponential_load_item.outputs[1],
                       target_port=_find_wrapper_port(editor, VarPowerFlowReferenceType.i_B, False))
    editor.apply_changes()

    generator_page_index = workspace.index_of_page(generator_page)
    assert generator_page_index >= 0
    workspace.close_tab_at(generator_page_index)

    load_page_index = workspace.index_of_page(load_page)
    assert load_page_index >= 0
    workspace.close_tab_at(load_page_index)
    assert session.get_last_active_workspace() is None
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()

    reopened_workspace = DynamicEditorWorkspaceWindow(session=session)
    reopened_workspace.show()
    reopened_page = reopened_workspace.open_dynamic_editor_for(api_object=load,
                                                               circuit=circuit,
                                                               preferred_mode=DynamicSimulationMode.EMT,
                                                               target_workspace=reopened_workspace)
    assert reopened_page is not None
    reopened_editor = reopened_page.editor
    assert reopened_editor is not None
    app.processEvents()

    internal_items = list(
        scene_item for scene_item in reopened_editor.scene.items()
        if (isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.subsys is not None
            and not dynamic_block_editor.is_root_interface_wrapper_block(
                block_model=scene_item.subsys,
                diagram=reopened_editor.diagram,
            ))
    )
    assert len(internal_items) == 1
    assert internal_items[0].subsys.name.startswith("EXP_Load_EMT")
    connection_refs = _collect_graphical_connection_refs(editor=reopened_editor)
    assert (VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_A) in connection_refs
    assert (VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_B) in connection_refs

    session.reset_for_tests()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize(
    ("intermediate_phases", "intermediate_apply"),
    [
        ([1, 2], False),
        ([1, 2], True),
        ([1, 3], False),
        ([1, 3], True),
        ([1], False),
        ([1], True),
    ],
)
def test_shared_line_generator_round_trip_reconciles_same_saved_model(intermediate_phases: list[int],
                                                                      intermediate_apply: bool) -> None:
    """Reopen grouped measurements after a shared-bus phase shrink and expansion.

    :param intermediate_phases: Intermediate static phase layout.
    :param intermediate_apply: Whether to persist the intermediate repaired measurements.
    :return: None.
    """
    editor, load, circuit, remote_bus = _build_connected_injection_editor(list((1, 2, 3)))
    template_item: graph.GenericBlockItem = _add_thevenin_item(editor, 240.0, 180.0)
    template_uid: int = template_item.subsys.uid
    editor.persist_changes_only()
    _dispose_editor(editor)
    phases: list[int]
    for phases in (intermediate_phases, list((1, 2, 3))):
        _apply_bus_phase_transition(circuit, load.bus, remote_bus, phases)
        # Opening a connected line must update the load's persistent interface too.
        dialog_models.initialize_connected_bus_models_for_editor_assignment(
            api_object=circuit.lines[0], circuit=circuit, var_factory=circuit.var_factory,
            mode=DynamicSimulationMode.EMT,
        )
        entry: DynamicEditorEntry | None = build_dynamic_editor_entry(load, circuit)
        assert entry is not None
        session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
        page: DynamicEditorTab = session.create_page(entry, DynamicSimulationMode.EMT)
        reopened: DynamicBlockEditorGUI | None = page.editor
        assert reopened is not None
        try:
            input_refs, output_refs = _expected_input_output_refs_for_phases(phases)
            _assert_root_wrapper_layers(reopened, input_refs, output_refs)
            assert template_uid in set(child.uid for child in reopened.main_block.children)
            if intermediate_apply:
                reopened.persist_changes_only()
            else:
                pass
        finally:
            page.prepare_to_delete()
            page.close()
            page.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
            _get_app().processEvents()


def test_shared_line_generator_round_trip_repeated_toggle_idempotent() -> None:
    """
    Verify repeated shared-bus topology toggling remains symmetric and duplicate-free.

    :return: None.
    """
    generator_editor, generator, circuit, remote_bus = _build_connected_injection_editor(active_phases=list([1, 2, 3]))
    line = circuit.lines[0]
    phase_sequence = [list([1, 2]), list([1, 2, 3]), list([1, 2]), list([1, 2, 3])]

    _add_thevenin_item(generator_editor, 240.0, 180.0)
    generator_editor.apply_changes()
    _dispose_editor(generator_editor)

    target_phases: list[int]
    for target_phases in phase_sequence:
        _apply_bus_phase_transition(circuit=circuit,
                                    bus=generator.bus,
                                    remote_bus=remote_bus,
                                    final_phases=target_phases)
        expected_inputs, expected_outputs = _expected_input_output_refs_for_phases(target_phases)
        assert get_bus_mask(grid=circuit, bus=generator.bus) == list([
            False,
            1 in target_phases,
            2 in target_phases,
            3 in target_phases,
        ])

        # Root editors consume bus models prepared before their construction.
        dialog_models.initialize_connected_bus_models_for_editor_assignment(
            api_object=line, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
        )
        line_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                            current_block=line.emt_model,
                                            root_block=line.emt_model,
                                            api_object=line,
                                            current_theme="Light",
                                            circuit=circuit,
                                            mode=DynamicSimulationMode.EMT,
                                            templates_list=list(),
                                            is_root_editor=True,
                                            modal=False)
        _dispose_editor(line_editor)

        # Root editors consume bus models prepared before their construction.
        dialog_models.initialize_connected_bus_models_for_editor_assignment(
            api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
        )
        generator_round_trip_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                                            current_block=generator.emt_model,
                                                            root_block=generator.emt_model,
                                                            api_object=generator,
                                                            current_theme="Light",
                                                            circuit=circuit,
                                                            mode=DynamicSimulationMode.EMT,
                                                            templates_list=list(),
                                                            is_root_editor=True,
                                                            modal=False)
        try:
            _assert_root_wrapper_layers(generator_round_trip_editor, expected_inputs, expected_outputs)
            assert _active_bus_voltage_refs(generator.bus) == tuple(sorted(
                expected_inputs,
                key=dynamic_block_editor.get_reference_sort_key,
            ))
        finally:
            _dispose_editor(generator_round_trip_editor)


@pytest.mark.parametrize("phases", ((0, 1, 2, 3), (1, 2, 3), (1, 2), (1, 3), (2, 3), (1,), (2,), (3,)))
def test_fresh_injection_measurements_follow_static_phase_layout(phases: tuple[int, ...]) -> None:
    """Build one measurement port per statically available phase, including neutral.

    :param phases: Static NABC phase layout at the requested editor opening.
    :return: None.
    """
    application: QtWidgets.QApplication = _get_app()
    circuit: MultiCircuit
    load: Load
    remote_bus: object
    phase_list: list[int]
    circuit, load, remote_bus, phase_list = _make_phase_transition_circuit(
        initial_phases=list(phases), final_phases=list(phases))
    assert get_bus_mask(grid=circuit, bus=load.bus) == list(index in phases for index in range(4))
    entry: DynamicEditorEntry | None = build_dynamic_editor_entry(load, circuit)
    assert entry is not None
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    page: DynamicEditorTab = session.create_page(entry, DynamicSimulationMode.EMT)
    editor: DynamicBlockEditorGUI | None = page.editor
    assert editor is not None
    try:
        expected_inputs, expected_outputs = _expected_input_output_refs_for_phases(phase_list)
        assert _collect_root_refs(editor.main_block) == (expected_inputs, expected_outputs)
        _assert_root_wrapper_layers(editor, expected_inputs, expected_outputs)
        assert not page.has_unapplied_changes
        assert editor.main_block is not load.emt_model
    finally:
        page.prepare_to_delete()
        page.close()
        page.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        application.processEvents()


def _build_real_branch_device(bus_from_model: Block, bus_to_model: Block) -> tuple[Line, MultiCircuit, VarFactory]:
    """
    Build one real EMT line device with controlled terminal bus EMT models.

    :param bus_from_model: EMT bus block for the from side.
    :param bus_to_model: EMT bus block for the to side.
    :return: Tuple with the device, circuit and variable factory.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = gce.Line(name="Line 1", bus_from=bus_from, bus_to=bus_to)
    circuit.add_line(line)
    line.bus_from.emt_model = bus_from_model
    line.bus_to.emt_model = bus_to_model
    line.emt_model = Block()
    line.emt_template = _make_template(list())
    var_factory = VarFactory()
    return line, circuit, var_factory


def _collect_graphical_connection_refs(editor: DynamicBlockEditorGUI) -> set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]]:
    """
    Collect visible semantic connection pairs from the editor scene.

    :param editor: Editor under test.
    :return: Set of ``(source_ref, target_ref)`` pairs for visible port wires.
    """
    connection_refs: set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]] = set()
    scene_item: object

    for scene_item in editor.scene.items():
        if isinstance(scene_item, graph.ConnectionItem):
            if scene_item.source_port is None or scene_item.target_port is None:
                pass
            elif scene_item.source_port.base_var is None or scene_item.target_port.base_var is None:
                pass
            elif scene_item.source_port.base_var.ref is None or scene_item.target_port.base_var.ref is None:
                pass
            else:
                connection_refs.add((scene_item.source_port.base_var.ref,
                                     scene_item.target_port.base_var.ref))
        else:
            pass

    return connection_refs


def test_add_connection_vars_emt_injection_uses_canonical_topology_mask() -> None:
    """
    Verify that an EMT injection exposes only the AC phases present in its bus.

    :return: None.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Gen Bus", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote Bus", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=list([1, 3]))
    var_factory = VarFactory()

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=load,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)

    bus_mapping: dict[VarPowerFlowReferenceType, Var | None] = load.bus.emt_model.external_mapping

    assert bus_mapping.get(VarPowerFlowReferenceType.v_N, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_B, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_C, None) is not None


def test_add_connection_vars_emt_injection_uses_canonical_neutral_mask() -> None:
    """
    Verify that the neutral connection ports appear only when the bus exposes neutral.

    :return: None.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Load Bus", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote Bus", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=list([1]))
    var_factory = VarFactory()

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=load,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)

    bus_mapping: dict[VarPowerFlowReferenceType, Var | None] = load.bus.emt_model.external_mapping

    assert bus_mapping.get(VarPowerFlowReferenceType.v_N, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_B, None) is None
    assert bus_mapping.get(VarPowerFlowReferenceType.v_C, None) is None


def test_root_emt_dc_injection_exposes_vdc_and_idc() -> None:
    """
    Verify one DC injection root editor shows both Vdc and Idc.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="DC Bus", Vnom=10.0, is_dc=True)
    circuit.add_bus(bus)
    load = gce.Load(name="DC Load")
    circuit.add_load(bus=bus, api_obj=load)
    load.bus.emt_model = _build_phase_bus_block(name="dc_bus", mask=list([False, False, False, False]), is_dc=True)
    load.emt_model = Block()

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=load.emt_model,
                                   root_block=load.emt_model,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    try:
        input_refs = [var.ref for var in editor.main_block.in_vars]
        output_refs = [var.ref for var in editor.main_block.out_vars]
        wrapper_input_refs, wrapper_output_refs = _collect_wrapper_refs(editor.main_block)

        assert input_refs.count(VarPowerFlowReferenceType.Vdc) == 1
        assert output_refs.count(VarPowerFlowReferenceType.Idc) == 1
        assert wrapper_input_refs == {VarPowerFlowReferenceType.Vdc}
        assert wrapper_output_refs == {VarPowerFlowReferenceType.Idc}
    finally:
        _dispose_editor(editor)


def test_template_backed_generator_preserves_template_block_across_topology_change() -> None:
    """
    Verify one template-backed generator keeps its template block after topology shrink.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    template_block_uids: set[int] = set(child.uid for child in generator.emt_model.children if child.name not in (BlockType.INPUT_CONN.name, BlockType.OUTPUT_CONN.name))
    assert len(template_block_uids) > 0

    _dispose_editor(editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, False])

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    reopened_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                            current_block=generator.emt_model,
                                            root_block=generator.emt_model,
                                            api_object=generator,
                                            current_theme="Light",
                                            circuit=circuit,
                                            mode=DynamicSimulationMode.EMT,
                                            templates_list=list(),
                                            is_root_editor=True,
                                            modal=False)
    try:
        input_refs, output_refs = _collect_root_refs(reopened_editor.main_block)
        surviving_block_uids: set[int] = set(child.uid for child in reopened_editor.main_block.children if child.name not in (BlockType.INPUT_CONN.name, BlockType.OUTPUT_CONN.name))

        assert input_refs == {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}
        assert output_refs == {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}
        assert template_block_uids == surviving_block_uids
        assert generator.emt_template is not None
    finally:
        _dispose_editor(reopened_editor)


def test_fresh_template_generator_places_measurements_around_content_and_fits_view() -> None:
    """
    Verify grouped measurements surround the template without moving it on first show.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3]),
    )
    try:
        content_items: list[graph.GenericBlockItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, graph.GenericBlockItem)
            and not isinstance(item, graph.ProtectedConnectionBlockItem)
        )
        assert len(content_items) == 1
        content_item: graph.GenericBlockItem = content_items[0]
        original_content_position: QtCore.QPointF = QtCore.QPointF(content_item.pos())

        _show_editor_with_workspace_sized_viewport(editor=editor)

        input_items: list[graph.ProtectedConnectionBlockItem | graph.MeasurementsItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, (graph.ProtectedConnectionBlockItem, graph.MeasurementsItem))
            and len(item.outputs) > 0
        )
        output_items: list[graph.ProtectedConnectionBlockItem | graph.MeasurementsItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, (graph.ProtectedConnectionBlockItem, graph.MeasurementsItem))
            and len(item.inputs) > 0
        )
        input_rect: QtCore.QRectF = QtCore.QRectF()
        output_rect: QtCore.QRectF = QtCore.QRectF()
        item: graph.ProtectedConnectionBlockItem | graph.MeasurementsItem

        for item in input_items:
            input_rect = item.sceneBoundingRect() if input_rect.isNull() else input_rect.united(item.sceneBoundingRect())
        for item in output_items:
            output_rect = item.sceneBoundingRect() if output_rect.isNull() else output_rect.united(item.sceneBoundingRect())

        content_rect: QtCore.QRectF = content_item.sceneBoundingRect()
        assert content_item.pos() == original_content_position
        assert input_rect.right() < content_rect.left()
        assert output_rect.left() > content_rect.right()
        assert len(input_items) == 1
        assert len(output_items) == 1
        assert editor.view.transform().m11() <= 1.0
        _assert_all_editor_blocks_are_inside_viewport(editor=editor)

        connection_item: graph.ConnectionItem
        route_path: QtGui.QPainterPath
        source_endpoint: QtCore.QPointF
        target_endpoint: QtCore.QPointF
        for connection_item in list(
                item for item in editor.scene.items()
                if isinstance(item, graph.ConnectionItem)):
            route_path = connection_item.path()
            assert route_path.isEmpty() is False
            source_endpoint = connection_item.source_port.scenePos()
            target_endpoint = connection_item.target_port.scenePos()
            assert QtCore.QLineF(route_path.pointAtPercent(0.0), source_endpoint).length() < 1e-6
            assert QtCore.QLineF(route_path.pointAtPercent(1.0), target_endpoint).length() < 1e-6
    finally:
        _dispose_editor(editor)


def test_complete_generator_template_bootstrap_separates_children_and_draws_shared_reference_wires() -> None:
    """
    Verify a fresh composite template is readable and graphically connected.

    :return: None.
    """
    editor: DynamicBlockEditorGUI = _build_complete_template_generator_editor()
    try:
        content_items: list[graph.GenericBlockItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, graph.GenericBlockItem)
            and not isinstance(item, graph.ProtectedConnectionBlockItem)
        )
        assert len(content_items) == 4

        first_index: int
        second_index: int
        for first_index, first_item in enumerate(content_items):
            for second_index in range(first_index + 1, len(content_items)):
                second_item: graph.GenericBlockItem = content_items[second_index]
                overlap: QtCore.QRectF = first_item.sceneBoundingRect().intersected(
                    second_item.sceneBoundingRect(),
                )
                assert overlap.isEmpty()

        content_uids: set[int] = set(
            item.subsys.uid for item in content_items
            if item.subsys is not None
        )
        expected_connections: set[tuple[int, int, int, int]] = set()
        expected_shared_reference_names: set[str] = set()
        source_item: graph.GenericBlockItem
        target_item: graph.GenericBlockItem

        for source_item in content_items:
            for target_item in content_items:
                if source_item.subsys is None or target_item.subsys is None:
                    pass
                elif source_item.subsys.uid == target_item.subsys.uid:
                    pass
                else:
                    pairs, power_flow_pairs = find_connections(source_item.subsys, target_item.subsys)
                    for source_var, target_var in pairs + power_flow_pairs:
                        source_port_index: int = source_item.subsys.out_vars.index(source_var)
                        target_port_index: int = target_item.subsys.in_vars.index(target_var)
                        expected_connections.add((source_item.subsys.uid,
                                                  source_port_index,
                                                  target_item.subsys.uid,
                                                  target_port_index))
                        if source_var.shared_ref is not None:
                            expected_shared_reference_names.add(source_var.shared_ref.name)
                        else:
                            pass

        visible_connections: set[tuple[int, int, int, int]] = set()
        scene_item: object
        for scene_item in editor.scene.items():
            if isinstance(scene_item, graph.ConnectionItem):
                source_block: Block | None = scene_item.source_port.subsystem.subsys
                target_block: Block | None = scene_item.target_port.subsystem.subsys
                if (source_block is not None
                        and target_block is not None
                        and source_block.uid in content_uids
                        and target_block.uid in content_uids):
                    visible_connections.add((source_block.uid,
                                             scene_item.source_port.index,
                                             target_block.uid,
                                             scene_item.target_port.index))
                else:
                    pass

        assert len(expected_connections) == 7
        assert expected_connections == visible_connections
        assert expected_shared_reference_names == {
            "IRPu_reference",
            "Te_reference",
            "Tm_reference",
            "V_pss_reference",
            "omega_reference",
            "v_f_reference",
        }

        _show_editor_with_workspace_sized_viewport(editor=editor)
        _assert_all_editor_blocks_are_inside_viewport(editor=editor)
    finally:
        _dispose_editor(editor)


def test_fresh_empty_line_groups_all_connection_vars_and_fits_view() -> None:
    """
    Verify a fresh ABC line exposes twelve ports in two grouped measurements.

    :return: None.
    """
    application: QtWidgets.QApplication = _get_app()
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
    )
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=line, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=var_factory,
                                   current_block=line.emt_model,
                                   root_block=line.emt_model,
                                   api_object=line,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    try:
        _show_editor_with_workspace_sized_viewport(editor=editor)
        wrapper_items: list[graph.ProtectedConnectionBlockItem | graph.MeasurementsItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, (graph.ProtectedConnectionBlockItem, graph.MeasurementsItem))
        )

        assert len(wrapper_items) == 2
        assert sum(len(item.inputs) + len(item.outputs) for item in wrapper_items) == 12
        # Bus identity propagation must preserve each terminal's semantic reference.
        assert all(
            variable.ref == reference
            for reference, variable in editor.main_block.external_mapping.items()
            if variable is not None
        )
        assert editor.view.transform().m11() <= 1.0
        _assert_all_editor_blocks_are_inside_viewport(editor=editor)
    finally:
        _dispose_editor(editor)


def test_initial_fit_preserves_manually_positioned_root_interface() -> None:
    """
    Verify first-show fitting never relocates a manually arranged interface.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3]),
    )
    _dispose_editor(editor)

    custom_positions: dict[int, tuple[float, float]] = dict()
    input_index: int = 0
    output_index: int = 0
    node_uid: int
    node: object

    for node_uid, node in generator.emt_model.diagram.node_data.items():
        if node.tpe == BlockType.INPUT_CONN.name:
            node.x = -420.0
            node.y = -80.0 + float(input_index) * 75.0
            input_index += 1
            custom_positions[node_uid] = (node.x, node.y)
        elif node.tpe == BlockType.OUTPUT_CONN.name:
            node.x = 520.0
            node.y = -80.0 + float(output_index) * 75.0
            output_index += 1
            custom_positions[node_uid] = (node.x, node.y)
        else:
            pass

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=generator, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    reopened_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                            current_block=generator.emt_model,
                                            root_block=generator.emt_model,
                                            api_object=generator,
                                            current_theme="Light",
                                            circuit=circuit,
                                            mode=DynamicSimulationMode.EMT,
                                            templates_list=list(),
                                            is_root_editor=True,
                                            modal=False)
    try:
        _show_editor_with_workspace_sized_viewport(editor=reopened_editor)

        for node_uid, expected_position in custom_positions.items():
            reopened_node = reopened_editor.diagram.node_data[node_uid]
            assert (reopened_node.x, reopened_node.y) == expected_position

        _assert_all_editor_blocks_are_inside_viewport(editor=reopened_editor)
    finally:
        _dispose_editor(reopened_editor)


def test_template_backed_generator_preflight_reconciles_without_reopening_editor() -> None:
    """
    Verify EMT preflight reconciles one template-backed generator after topology changes.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    _dispose_editor(editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, False])

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2, 3]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])

    logger = circuit.check_emt_models()
    assert logger.has_errors() is False
    assert generator.bus.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_C, None) is not None
    assert len(generator.emt_model.connection_intents) > 0


def test_saved_load_preflight_preserves_live_bus_bindings_after_ab_abc_cycle() -> None:
    """
    Keep one editor-saved load bound to the live bus after an AB-to-ABC cycle.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit
    load: Load
    remote_bus: object
    circuit, load, remote_bus, _final_phases = _make_phase_transition_circuit(
        initial_phases=list([1, 2, 3]),
        final_phases=list([1, 2]),
    )
    line: Line = circuit.lines[0]
    line_template: EmtModelTemplate = get_pi_line_emt_template(
        vf=circuit.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name="PiTemplate",
    )
    line.emt_template = line_template
    line.emt_model = duplicate_block(line_template.block, var_factory=circuit.var_factory)
    load.emt_model = Block()

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=load.emt_model,
                                   root_block=load.emt_model,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    gain_blocks_by_ref: dict[VarPowerFlowReferenceType, Block] = dict()
    voltage_ref: VarPowerFlowReferenceType
    current_ref: VarPowerFlowReferenceType
    gain_item: graph.GenericBlockItem
    gain_block: Block
    y_position: float = 80.0
    try:
        for voltage_ref, current_ref in [
            (VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.i_A),
            (VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.i_B),
            (VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.i_C),
        ]:
            gain_item, _input_uid, _output_uid, _input_connection_uid, _output_connection_uid = (
                _build_connected_gain_phase(editor=editor,
                                            voltage_reference=voltage_ref,
                                            current_reference=current_ref,
                                            x_pos=260.0,
                                            y_pos=y_position)
            )
            assert gain_item.subsys is not None
            gain_blocks_by_ref[voltage_ref] = gain_item.subsys
            y_position += 140.0

        editor.apply_changes()
    finally:
        _dispose_editor(editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=load.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2]))
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    intermediate_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                                 current_block=load.emt_model,
                                                 root_block=load.emt_model,
                                                 api_object=load,
                                                 current_theme="Light",
                                                 circuit=circuit,
                                                 mode=DynamicSimulationMode.EMT,
                                                 templates_list=list(),
                                                 is_root_editor=True,
                                                 modal=False)
    _dispose_editor(intermediate_editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=load.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2, 3]))
    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=load, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    restored_editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                             current_block=load.emt_model,
                                             root_block=load.emt_model,
                                             api_object=load,
                                             current_theme="Light",
                                             circuit=circuit,
                                             mode=DynamicSimulationMode.EMT,
                                             templates_list=list(),
                                             is_root_editor=True,
                                             modal=False)
    _dispose_editor(restored_editor)

    logger: Logger = circuit.check_emt_models()
    assert logger.has_errors() is False, str(logger)
    first_connection_count: int = sum(
        len(connection_list)
        for connection_list in circuit.var_factory.get_connections_dict().values()
    )
    repeated_logger: Logger = circuit.check_emt_models()
    repeated_connection_count: int = sum(
        len(connection_list)
        for connection_list in circuit.var_factory.get_connections_dict().values()
    )
    assert repeated_logger.has_errors() is False, str(repeated_logger)
    assert repeated_connection_count == first_connection_count

    device_var: Var | None
    bus_var: Var | None
    for voltage_ref in [
        VarPowerFlowReferenceType.v_A,
        VarPowerFlowReferenceType.v_B,
        VarPowerFlowReferenceType.v_C,
    ]:
        device_var = load.emt_model.external_mapping.get(voltage_ref, None)
        bus_var = load.bus.emt_model.external_mapping.get(voltage_ref, None)
        assert device_var is not None
        assert bus_var is not None
        assert device_var.uid == bus_var.uid
        gain_block = gain_blocks_by_ref[voltage_ref]
        assert gain_block.in_vars[0].uid == bus_var.uid


def test_template_backed_generator_preflight_does_not_materialize_absent_neutral() -> None:
    """
    Verify an ABC bus keeps template neutral intents dormant during EMT preflight.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(
        active_phases=list([1, 2, 3]),
    )
    _dispose_editor(editor)

    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])
    phi_v_var: Var | None = generator.emt_model.external_mapping.get(
        VarPowerFlowReferenceType.phi_v,
        None,
    )
    assert phi_v_var is not None
    logger = circuit.check_emt_models()

    assert logger.has_errors() is False, str(logger)
    assert generator.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_N, None) is None
    assert generator.emt_model.external_mapping.get(VarPowerFlowReferenceType.i_N, None) is None
    assert generator.emt_model.external_mapping.get(VarPowerFlowReferenceType.phi_v, None) == phi_v_var
    assert VarPowerFlowReferenceType.v_N not in set(var.ref for var in generator.emt_model.in_vars)
    assert VarPowerFlowReferenceType.i_N not in set(var.ref for var in generator.emt_model.out_vars)


def test_template_backed_generator_preflight_reconciles_shrink_expand_cycle() -> None:
    """
    Verify EMT preflight restores one template-backed generator across one shrink/expand cycle.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    _dispose_editor(editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, False])
    shrink_logger = circuit.check_emt_models()
    assert shrink_logger.has_errors() is False, str(shrink_logger)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2, 3]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])
    variant_logger = circuit.check_emt_models()
    assert variant_logger.has_errors() is False, str(variant_logger)


def test_template_backed_generator_preflight_reconciles_ac_variant_cycle() -> None:
    """
    Verify EMT preflight restores one template-backed generator across one AC variant cycle.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    _dispose_editor(editor)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 3]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, False, True])
    assert circuit.check_emt_models().has_errors() is False

    _apply_bus_phase_transition(circuit=circuit,
                                bus=generator.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2, 3]))
    assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])
    assert circuit.check_emt_models().has_errors() is False


def test_branch_preflight_reconciles_without_reopening_editor() -> None:
    """
    Verify EMT preflight reconciles one branch-like EMT model after topology changes.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=False).emt_model,
    )

    vf_a: Var = _make_var("vf_A_root", VarPowerFlowReferenceType.vf_A)
    vf_b: Var = _make_var("vf_B_root", VarPowerFlowReferenceType.vf_B)
    vf_c: Var = _make_var("vf_C_root", VarPowerFlowReferenceType.vf_C)
    vt_a: Var = _make_var("vt_A_root", VarPowerFlowReferenceType.vt_A)
    vt_b: Var = _make_var("vt_B_root", VarPowerFlowReferenceType.vt_B)
    if_a: Var = _make_var("if_A_root", VarPowerFlowReferenceType.if_A)
    if_b: Var = _make_var("if_B_root", VarPowerFlowReferenceType.if_B)
    if_c: Var = _make_var("if_C_root", VarPowerFlowReferenceType.if_C)
    it_a: Var = _make_var("it_A_root", VarPowerFlowReferenceType.it_A)
    it_b: Var = _make_var("it_B_root", VarPowerFlowReferenceType.it_B)
    internal_in_from: Var = _make_var("internal_if_A", VarPowerFlowReferenceType.if_A)
    internal_out_from: Var = _make_var("internal_vf_A", VarPowerFlowReferenceType.vf_A)
    internal_in_to: Var = _make_var("internal_it_B", VarPowerFlowReferenceType.it_B)
    internal_out_to: Var = _make_var("internal_vt_B", VarPowerFlowReferenceType.vt_B)
    internal_from = Block(name="InternalFrom", uid=8101, in_vars=list([internal_in_from]), out_vars=list([internal_out_from]))
    internal_to = Block(name="InternalTo", uid=8102, in_vars=list([internal_in_to]), out_vars=list([internal_out_to]))

    line.emt_model.in_vars = list([vf_a, vf_b, vf_c, vt_a, vt_b])
    line.emt_model.out_vars = list([if_a, if_b, if_c, it_a, it_b])
    line.emt_model.children = list([internal_from, internal_to])
    line.emt_model.external_mapping = dict({
        VarPowerFlowReferenceType.vf_A: vf_a,
        VarPowerFlowReferenceType.vf_B: vf_b,
        VarPowerFlowReferenceType.vf_C: vf_c,
        VarPowerFlowReferenceType.vt_A: vt_a,
        VarPowerFlowReferenceType.vt_B: vt_b,
        VarPowerFlowReferenceType.if_A: if_a,
        VarPowerFlowReferenceType.if_B: if_b,
        VarPowerFlowReferenceType.if_C: if_c,
        VarPowerFlowReferenceType.it_A: it_a,
        VarPowerFlowReferenceType.it_B: it_b,
    })
    line.emt_model.connection_intents = list([
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.vf_A,
                                direction=DynamicConnectionIntentDirection.INPUT,
                                internal_block_uid=internal_from.uid,
                                internal_variable_uid=internal_in_from.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.if_A,
                                direction=DynamicConnectionIntentDirection.OUTPUT,
                                internal_block_uid=internal_from.uid,
                                internal_variable_uid=internal_out_from.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.vt_B,
                                direction=DynamicConnectionIntentDirection.INPUT,
                                internal_block_uid=internal_to.uid,
                                internal_variable_uid=internal_in_to.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.it_B,
                                direction=DynamicConnectionIntentDirection.OUTPUT,
                                internal_block_uid=internal_to.uid,
                                internal_variable_uid=internal_out_to.non_mutable_uid),
    ])

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=line,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)
    attach_emt_model_to_buses(device=line,
                              model=line.emt_model,
                              var_factory=var_factory)

    _apply_line_phase_transition(line=line,
                                 final_phases=list([1, 2]))
    assert get_bus_mask(grid=circuit, bus=line.bus_from) == list([False, True, True, False])
    assert get_bus_mask(grid=circuit, bus=line.bus_to) == list([False, True, True, False])
    shrink_logger = circuit.check_emt_models()
    assert shrink_logger.has_errors() is False, str(shrink_logger)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None

    _apply_line_phase_transition(line=line,
                                 final_phases=list([1, 2, 3]))
    assert get_bus_mask(grid=circuit, bus=line.bus_from) == list([False, True, True, True])
    assert get_bus_mask(grid=circuit, bus=line.bus_to) == list([False, True, True, True])
    assert circuit.check_emt_models().has_errors() is False
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is not None
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None


def test_branch_preflight_reconciles_from_and_to_sides_independently() -> None:
    """
    Verify supported branch-side refs remain stable across branch preflight cycles.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=False).emt_model,
    )

    vf_a: Var = _make_var("vf_A_root", VarPowerFlowReferenceType.vf_A)
    vf_b: Var = _make_var("vf_B_root", VarPowerFlowReferenceType.vf_B)
    vf_c: Var = _make_var("vf_C_root", VarPowerFlowReferenceType.vf_C)
    vt_a: Var = _make_var("vt_A_root", VarPowerFlowReferenceType.vt_A)
    vt_b: Var = _make_var("vt_B_root", VarPowerFlowReferenceType.vt_B)
    if_a: Var = _make_var("if_A_root", VarPowerFlowReferenceType.if_A)
    if_b: Var = _make_var("if_B_root", VarPowerFlowReferenceType.if_B)
    if_c: Var = _make_var("if_C_root", VarPowerFlowReferenceType.if_C)
    it_a: Var = _make_var("it_A_root", VarPowerFlowReferenceType.it_A)
    it_b: Var = _make_var("it_B_root", VarPowerFlowReferenceType.it_B)
    internal_in_from: Var = _make_var("internal_if_A", VarPowerFlowReferenceType.if_A)
    internal_out_from: Var = _make_var("internal_vf_A", VarPowerFlowReferenceType.vf_A)
    internal_in_to: Var = _make_var("internal_it_B", VarPowerFlowReferenceType.it_B)
    internal_out_to: Var = _make_var("internal_vt_B", VarPowerFlowReferenceType.vt_B)
    internal_from = Block(name="InternalFrom", uid=8201, in_vars=list([internal_in_from]), out_vars=list([internal_out_from]))
    internal_to = Block(name="InternalTo", uid=8202, in_vars=list([internal_in_to]), out_vars=list([internal_out_to]))

    line.emt_model.in_vars = list([vf_a, vf_b, vf_c, vt_a, vt_b])
    line.emt_model.out_vars = list([if_a, if_b, if_c, it_a, it_b])
    line.emt_model.children = list([internal_from, internal_to])
    line.emt_model.external_mapping = dict({
        VarPowerFlowReferenceType.vf_A: vf_a,
        VarPowerFlowReferenceType.vf_B: vf_b,
        VarPowerFlowReferenceType.vf_C: vf_c,
        VarPowerFlowReferenceType.vt_A: vt_a,
        VarPowerFlowReferenceType.vt_B: vt_b,
        VarPowerFlowReferenceType.if_A: if_a,
        VarPowerFlowReferenceType.if_B: if_b,
        VarPowerFlowReferenceType.if_C: if_c,
        VarPowerFlowReferenceType.it_A: it_a,
        VarPowerFlowReferenceType.it_B: it_b,
    })
    line.emt_model.connection_intents = list([
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.vf_A,
                                direction=DynamicConnectionIntentDirection.INPUT,
                                internal_block_uid=internal_from.uid,
                                internal_variable_uid=internal_in_from.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.if_A,
                                direction=DynamicConnectionIntentDirection.OUTPUT,
                                internal_block_uid=internal_from.uid,
                                internal_variable_uid=internal_out_from.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.vt_B,
                                direction=DynamicConnectionIntentDirection.INPUT,
                                internal_block_uid=internal_to.uid,
                                internal_variable_uid=internal_in_to.non_mutable_uid),
        DynamicConnectionIntent(origin=DynamicConnectionIntentOrigin.USER,
                                root_reference=VarPowerFlowReferenceType.it_B,
                                direction=DynamicConnectionIntentDirection.OUTPUT,
                                internal_block_uid=internal_to.uid,
                                internal_variable_uid=internal_out_to.non_mutable_uid),
    ])

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=line,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)
    attach_emt_model_to_buses(device=line,
                              model=line.emt_model,
                              var_factory=var_factory)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))
    line.bus_to.emt_model = _build_phase_bus_block(name="bus_to_ab", mask=list([False, True, True, False]))
    assert circuit.check_emt_models().has_errors() is False
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_A, None) is not None
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.if_A, None) is not None

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_abc", mask=list([False, True, True, True]))
    line.bus_to.emt_model = _build_phase_bus_block(name="bus_to_ab_restore", mask=list([False, True, True, False]))
    assert circuit.check_emt_models().has_errors() is False
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is not None
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None


def test_find_connections_matches_vsc_dc_input_with_generic_dc_port() -> None:
    """
    Verify that generic DC voltage references still match power-flow connections.

    :return: None.
    """
    bus_connection_block = Block(out_vars=list([
        _make_var("Vdc_DC_Bus", VarPowerFlowReferenceType.Vdc),
    ]))
    converter_block = Block(in_vars=list([
        _make_var("v_dc_pseudo_converter_emt", VarPowerFlowReferenceType.Vdc),
    ]))

    pairs, power_flow_pairs = find_connections(bus_connection_block, converter_block)

    assert len(pairs) == 0
    assert len(power_flow_pairs) == 1
    assert power_flow_pairs[0][0].ref == VarPowerFlowReferenceType.Vdc
    assert power_flow_pairs[0][1].ref == VarPowerFlowReferenceType.Vdc


def test_attach_emt_model_to_buses_preserves_side_specific_root_mapping() -> None:
    """
    Verify that EMT branch attach keeps side-specific root refs on the saved model.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
    )

    vf_a: Var = _make_var("vf_A_root", VarPowerFlowReferenceType.vf_A)
    vf_b: Var = _make_var("vf_B_root", VarPowerFlowReferenceType.vf_B)
    vt_a: Var = _make_var("vt_A_root", VarPowerFlowReferenceType.vt_A)
    vt_b: Var = _make_var("vt_B_root", VarPowerFlowReferenceType.vt_B)
    if_a: Var = _make_var("if_A_root", VarPowerFlowReferenceType.if_A)
    if_b: Var = _make_var("if_B_root", VarPowerFlowReferenceType.if_B)
    it_a: Var = _make_var("it_A_root", VarPowerFlowReferenceType.it_A)
    it_b: Var = _make_var("it_B_root", VarPowerFlowReferenceType.it_B)

    line.emt_model.in_vars = list([vf_a, vf_b, vt_a, vt_b])
    line.emt_model.out_vars = list([if_a, if_b, it_a, it_b])
    line.emt_model.external_mapping = dict({
        VarPowerFlowReferenceType.vf_A: vf_a,
        VarPowerFlowReferenceType.vf_B: vf_b,
        VarPowerFlowReferenceType.vt_A: vt_a,
        VarPowerFlowReferenceType.vt_B: vt_b,
        VarPowerFlowReferenceType.if_A: if_a,
        VarPowerFlowReferenceType.if_B: if_b,
        VarPowerFlowReferenceType.it_A: it_a,
        VarPowerFlowReferenceType.it_B: it_b,
    })

    dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=line,
                                                                        circuit=circuit,
                                                                        var_factory=var_factory,
                                                                        mode=DynamicSimulationMode.EMT)
    attach_emt_model_to_buses(device=line,
                              model=line.emt_model,
                              var_factory=var_factory)

    mapping: dict[VarPowerFlowReferenceType, Var | None] = line.emt_model.external_mapping

    assert mapping.get(VarPowerFlowReferenceType.vf_A, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vf_B, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vt_A, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.vt_B, None) is not None
    assert mapping.get(VarPowerFlowReferenceType.v_A, None) is None
    assert mapping.get(VarPowerFlowReferenceType.v_B, None) is None


def test_branch_template_open_keeps_from_and_to_voltage_refs_separate() -> None:
    """
    Verify branch template-open auto wiring preserves vf/vt side separation.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = gce.Line(name="Line 1", bus_from=bus_from, bus_to=bus_to)
    circuit.add_line(obj=line)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from", mask=list([False, True, True, True]))
    line.bus_to.emt_model = _build_phase_bus_block(name="bus_to", mask=list([False, True, True, True]))
    line.emt_model = duplicate_block(get_pi_line_emt_template(vf=circuit.var_factory,
                                                               phN=False,
                                                               phA=True,
                                                               phB=True,
                                                               phC=True,
                                                               name="Pi").block,
                                     var_factory=circuit.var_factory)

    # Root editors consume bus models prepared before their construction.
    dialog_models.initialize_connected_bus_models_for_editor_assignment(
        api_object=line, circuit=circuit, var_factory=circuit.var_factory, mode=DynamicSimulationMode.EMT,
    )
    editor = DynamicBlockEditorGUI(var_factory=circuit.var_factory,
                                   current_block=line.emt_model,
                                   root_block=line.emt_model,
                                   api_object=line,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    try:
        generic_items = [item for item in editor.scene.items() if isinstance(item, graph.GenericBlockItem) and item.subsys is not None]
        branch_items = [item for item in generic_items if len(item.inputs) >= 6]
        assert len(branch_items) >= 1
        branch_item = branch_items[0]
        input_refs = [port.base_var.ref if port.base_var is not None else None for port in branch_item.inputs]

        assert VarPowerFlowReferenceType.vf_A in input_refs
        assert VarPowerFlowReferenceType.vf_B in input_refs
        assert VarPowerFlowReferenceType.vf_C in input_refs
        assert VarPowerFlowReferenceType.vt_A in input_refs
        assert VarPowerFlowReferenceType.vt_B in input_refs
        assert VarPowerFlowReferenceType.vt_C in input_refs
    finally:
        _dispose_editor(editor)
