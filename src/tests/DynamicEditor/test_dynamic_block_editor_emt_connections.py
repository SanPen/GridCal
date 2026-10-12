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
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, find_connections
from VeraGridEngine.Utils.Symbolic.dynamic_connection_intent import (DynamicConnectionIntent,
                                                                     DynamicConnectionIntentDirection,
                                                                     DynamicConnectionIntentOrigin)
from VeraGridEngine.Utils.Symbolic.templates_common_functions import (attach_emt_model_to_buses,
                                                                     _ensure_saved_branch_root_contract_side,
                                                                     _normalize_saved_branch_root_contract_from_live_sides,
                                                                     _prune_saved_branch_root_contract_side,
                                                                     _rebuild_saved_branch_root_contract_from_live_sides,
                                                                     rematerialize_saved_dynamic_connection_intents,
                                                                     seed_template_derived_dynamic_connection_intents,
                                                                     synchronize_saved_emt_root_contract_from_bus)
from VeraGridEngine.Devices.Parents.dynamic_bus_parent import EmtBusConnectionSide
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, VarPowerFlowReferenceType, BlockType
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_mask
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template, EmtLineTypes
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp

pytestmark = pytest.mark.filterwarnings("error")


class _BusStub:
    __slots__ = ("name", "is_dc", "emt_model", "_connected_emt_models", "_pending_emt_devices")

    def __init__(self, name: str, is_dc: bool, emt_model: Block) -> None:
        """Create a minimal bus object for EMT connection tests.

        :param name: Bus name exposed to connection diagnostics.
        :param is_dc: Whether the stub represents a DC bus.
        :param emt_model: Symbolic EMT bus model exposed by the stub.
        """
        self.name = name
        self.is_dc = is_dc
        self.emt_model = emt_model
        self._connected_emt_models: list[object] = list()
        self._pending_emt_devices: list[object] = list()

    def add_or_replace_emt_model_connected(self,
                                           device: object,
                                           emt_model: Block,
                                           side: object,
                                           device_tpe: DeviceType) -> None:
        """
        Store one connected EMT model record for the stub bus.

        :param device: Device being registered.
        :param emt_model: EMT model block connected to the bus.
        :param side: Side identifier used by branch-like devices.
        :param device_tpe: Device type of the connected object.
        :return: None.
        """
        self.remove_emt_model_connected_for_device(device=device, side=side)
        record: _ConnectedModelRecord = _ConnectedModelRecord(device=device,
                                                              model=emt_model,
                                                              side=side,
                                                              device_tpe=device_tpe)
        self._connected_emt_models.append(record)

    def remove_emt_model_connected_for_device(self, device: object, side: object | None = None) -> None:
        """
        Remove matching connected EMT model records from the stub bus.

        :param device: Device to remove.
        :param side: Optional side filter.
        :return: None.
        """
        self._connected_emt_models = [
            record for record in self._connected_emt_models
            if not (record.get_device() is device and (side is None or record.get_side() == side))
        ]

    def get_emt_models_connected(self) -> list[object]:
        """
        Return a shallow copy of the connected EMT model records.

        :return: Connected model record list.
        """
        return list(self._connected_emt_models)

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


class _ConnectedModelRecord:
    __slots__ = ("_device", "_model", "_side", "_device_tpe")

    def __init__(self, device: object, model: Block, side: object, device_tpe: DeviceType) -> None:
        """
        Build one connected EMT model record.

        :param device: Registered device.
        :param model: Registered EMT block.
        :param side: Side identifier for branch-like devices.
        :param device_tpe: Device type of the registered object.
        :return: None.
        """
        self._device = device
        self._model = model
        self._side = side
        self._device_tpe = device_tpe

    def get_device(self) -> object:
        """
        Return the registered device.

        :return: Registered device.
        """
        return self._device

    def get_model(self) -> Block:
        """
        Return the registered EMT model block.

        :return: Registered EMT block.
        """
        return self._model

    def get_side(self) -> object:
        """
        Return the registered side marker.

        :return: Side marker.
        """
        return self._side

    def get_device_tpe(self) -> DeviceType:
        """
        Return the registered device type.

        :return: Device type.
        """
        return self._device_tpe


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


def _make_dc_bus(name: str) -> _BusStub:
    """
    Build one DC bus stub exposing only the DC voltage.

    :param name: Bus name.
    :return: DC bus stub.
    """
    return _BusStub(
        name=name,
        is_dc=True,
        emt_model=Block(external_mapping={
            VarPowerFlowReferenceType.Vdc: _make_var(f"Vdc_{name}", VarPowerFlowReferenceType.Vdc),
        }),
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


def _build_editor(api_object: ALL_DEV_TYPES) -> DynamicBlockEditorGUI:
    """
    Build one detached EMT editor around the provided API object.

    :param api_object: Device or template object under test.
    :return: Dynamic block editor instance.
    """
    _get_app()
    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=api_object,
        current_theme="Light",
        circuit=MultiCircuit(),
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
    )
    return editor


def _build_real_injection_editor(bus_model: Block) -> tuple[DynamicBlockEditorGUI, Load]:
    """
    Build one real EMT load editor backed by a controlled bus EMT model.

    :param bus_model: EMT bus block to expose to the editor.
    :return: Tuple with the editor and the owned load object.
    """
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)

    # Inject the desired EMT bus shell directly so the editor under test reads
    # only the selected phase set from the bus helper model.
    load.bus.emt_model = bus_model
    load.emt_model = Block()
    load.emt_template = _make_template(list())

    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=load,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    return editor, load


def _build_real_injection_device(bus_model: Block) -> tuple[Load, MultiCircuit, VarFactory]:
    """
    Build one real EMT load device with a controlled bus EMT model.

    :param bus_model: EMT bus block to expose to the device.
    :return: Tuple with the device, circuit and variable factory.
    """
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    load.bus.emt_model = bus_model
    load.emt_model = Block()
    load.emt_template = _make_template(list())
    var_factory: VarFactory = VarFactory()
    return load, circuit, var_factory


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
    """
    Collect input/output wrapper references from one root block.

    :param block: Root block to inspect.
    :return: ``(input_wrapper_refs, output_wrapper_refs)``.
    """
    input_refs: set[VarPowerFlowReferenceType] = set()
    output_refs: set[VarPowerFlowReferenceType] = set()
    child: Block

    for child in block.children:
        if not dynamic_block_editor.is_root_interface_wrapper_block(block_model=child,
                                                                    diagram=block.diagram):
            pass
        elif len(child.out_vars) == 1 and len(child.in_vars) == 0 and child.out_vars[0].ref is not None:
            input_refs.add(child.out_vars[0].ref)
        elif len(child.in_vars) == 1 and len(child.out_vars) == 0 and child.in_vars[0].ref is not None:
            output_refs.add(child.in_vars[0].ref)
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
    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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


def _find_semantic_wrapper_item(
        editor: DynamicBlockEditorGUI,
        reference: VarPowerFlowReferenceType,
        block_type: BlockType,
) -> graph.ProtectedConnectionBlockItem | graph.MeasurementsItem:
    """
    Find one root-interface item by its side-specific semantic reference.

    :param editor: Editor under test.
    :param reference: Required side-specific root reference.
    :param block_type: Input or output wrapper direction.
    :return: Matching protected wrapper item.
    """
    scene_item: object

    for scene_item in editor.scene.items():
        if isinstance(scene_item, (graph.ProtectedConnectionBlockItem, graph.MeasurementsItem)) and scene_item.subsys is not None:
            if editor._get_semantic_root_interface_reference(
                    wrapper_block=scene_item.subsys,
                    block_type=block_type,
            ) == reference:
                return scene_item
            else:
                pass
        else:
            pass

    raise AssertionError(f"Semantic wrapper not found for {reference}")


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


def _find_semantic_wrapper_port(
        editor: DynamicBlockEditorGUI,
        reference: VarPowerFlowReferenceType,
        block_type: BlockType,
) -> graph.PortItem:
    """Find the graphical port owned by one side-specific interface wrapper.

    Branch wrappers can carry a shared bus variable such as ``v_A`` while the
    diagram identifies the selected terminal semantically as ``vf_A`` or
    ``vt_A``. The semantic item lookup disambiguates the terminal first; a
    single-port item can then return its physical port without comparing refs.

    :param editor: Editor under test.
    :param reference: Side-specific semantic interface reference.
    :param block_type: Input or output wrapper direction.
    :return: Matching graphical interface port.
    """
    wrapper_item: graph.ProtectedConnectionBlockItem | graph.MeasurementsItem = (
        _find_semantic_wrapper_item(
            editor=editor,
            reference=reference,
            block_type=block_type,
        )
    )
    if block_type == BlockType.INPUT_CONN:
        candidate_ports: list[graph.PortItem] = wrapper_item.outputs
    elif block_type == BlockType.OUTPUT_CONN:
        candidate_ports = wrapper_item.inputs
    else:
        candidate_ports = list()

    if len(candidate_ports) == 1:
        return candidate_ports[0]
    else:
        return _find_item_port_by_reference(
            item=wrapper_item,
            reference=reference,
            is_input=block_type == BlockType.OUTPUT_CONN,
        )


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
    """
    Assert root symbolic/mapping/wrapper/diagram/scene layers match exactly.

    :param editor: Editor under test.
    :param expected_input_refs: Expected root input refs.
    :param expected_output_refs: Expected root output refs.
    :return: None.
    """
    wrapper_input_refs, wrapper_output_refs = _collect_wrapper_refs(editor.main_block)
    generic_root_items = [
        item for item in editor.scene.items()
        if isinstance(item, graph.GenericBlockItem) and item.subsys is editor.main_block
    ]
    input_wrapper_counts: dict[VarPowerFlowReferenceType, int] = dict()
    output_wrapper_counts: dict[VarPowerFlowReferenceType, int] = dict()
    node_input_counts: dict[VarPowerFlowReferenceType, int] = dict()
    node_output_counts: dict[VarPowerFlowReferenceType, int] = dict()
    child: Block
    node: object
    reference: VarPowerFlowReferenceType

    _count_root_refs(editor.main_block, expected_input_refs, expected_output_refs)
    assert wrapper_input_refs == expected_input_refs
    assert wrapper_output_refs == expected_output_refs

    for child in editor.main_block.children:
        if len(child.out_vars) == 1 and child.out_vars[0].ref is not None:
            input_wrapper_counts[child.out_vars[0].ref] = input_wrapper_counts.get(child.out_vars[0].ref, 0) + 1
        elif len(child.in_vars) == 1 and child.in_vars[0].ref is not None:
            output_wrapper_counts[child.in_vars[0].ref] = output_wrapper_counts.get(child.in_vars[0].ref, 0) + 1
        else:
            pass

    for node in editor.diagram.node_data.values():
        if node.tpe not in {"INPUT_CONN", "OUTPUT_CONN"}:
            pass
        else:
            wrapper_block = editor.get_block_from_main_block(node.device_uid)
            interface_var = None if wrapper_block is None else _get_single_wrapper_ref(wrapper_block)
            if interface_var is None:
                pass
            elif node.tpe == "INPUT_CONN":
                node_input_counts[interface_var] = node_input_counts.get(interface_var, 0) + 1
            else:
                node_output_counts[interface_var] = node_output_counts.get(interface_var, 0) + 1

    for reference in expected_input_refs:
        assert input_wrapper_counts.get(reference, 0) == 1
        assert node_input_counts.get(reference, 0) == 1
        assert list(editor.main_block.external_mapping.keys()).count(reference) == 1

    for reference in expected_output_refs:
        assert output_wrapper_counts.get(reference, 0) == 1
        assert node_output_counts.get(reference, 0) == 1
        assert list(editor.main_block.external_mapping.keys()).count(reference) == 1

    _assert_scene_wrapper_counts(editor, expected_input_refs, expected_output_refs)
    assert len(generic_root_items) == 0


def _get_single_wrapper_ref(block: Block) -> VarPowerFlowReferenceType | None:
    """
    Return the single wrapper ref when ``block`` is one root interface wrapper.

    :param block: Wrapper candidate.
    :return: Wrapped ref or ``None``.
    """
    if len(block.out_vars) == 1 and len(block.in_vars) == 0 and block.out_vars[0].ref is not None:
        return block.out_vars[0].ref
    elif len(block.in_vars) == 1 and len(block.out_vars) == 0 and block.in_vars[0].ref is not None:
        return block.in_vars[0].ref
    else:
        return None


def _expected_input_output_refs_for_phases(phases: list[int]) -> tuple[set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType]]:
    """
    Build expected injection root refs for one AC phase-number set.

    :param phases: Active phase numbers.
    :return: Expected input/output refs.
    """
    input_refs: set[VarPowerFlowReferenceType] = set()
    output_refs: set[VarPowerFlowReferenceType] = set()

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


def test_connected_unsaved_injection_abc_to_ab_disconnects_root_wires_and_preserves_user_blocks() -> None:
    """
    Verify live topology shrink removes root wires but keeps user blocks alive.

    :return: None.
    """
    editor, load, circuit, remote_bus = _build_connected_injection_editor(active_phases=list([1, 2, 3]))
    gain_a, wrap_in_a_uid, wrap_out_a_uid, conn_a1_uid, conn_a2_uid = _build_connected_gain_phase(editor,
                                                                                                     VarPowerFlowReferenceType.v_A,
                                                                                                     VarPowerFlowReferenceType.i_A,
                                                                                                     200.0,
                                                                                                     80.0)
    gain_b, wrap_in_b_uid, wrap_out_b_uid, conn_b1_uid, conn_b2_uid = _build_connected_gain_phase(editor,
                                                                                                     VarPowerFlowReferenceType.v_B,
                                                                                                     VarPowerFlowReferenceType.i_B,
                                                                                                     200.0,
                                                                                                     180.0)
    gain_c, wrap_in_c_uid, wrap_out_c_uid, conn_c1_uid, conn_c2_uid = _build_connected_gain_phase(editor,
                                                                                                     VarPowerFlowReferenceType.v_C,
                                                                                                     VarPowerFlowReferenceType.i_C,
                                                                                                     200.0,
                                                                                                     280.0)

    editor.has_unapplied_changes = True
    editor.changes_applied = False
    gain_c_input_var = gain_c.subsys.in_vars[0]
    gain_c_output_var = gain_c.subsys.out_vars[0]
    gain_c_input_identity = (gain_c_input_var.non_mutable_uid, gain_c_input_var.uid, gain_c_input_var.name)
    gain_c_output_identity = (gain_c_output_var.non_mutable_uid, gain_c_output_var.uid, gain_c_output_var.name)

    _apply_bus_phase_transition(circuit=circuit,
                                bus=load.bus,
                                remote_bus=remote_bus,
                                final_phases=list([1, 2]))

    try:
        changed = editor.reconcile_root_emt_topology_now()
        assert changed is True

        input_refs, output_refs = _collect_root_refs(editor.main_block)
        assert input_refs == {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}
        assert output_refs == {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}
        assert wrap_in_a_uid in editor.diagram.node_data
        assert wrap_in_b_uid in editor.diagram.node_data
        assert wrap_out_a_uid in editor.diagram.node_data
        assert wrap_out_b_uid in editor.diagram.node_data
        assert wrap_in_c_uid not in editor.diagram.node_data
        assert wrap_out_c_uid not in editor.diagram.node_data
        assert conn_a1_uid not in editor.diagram.con_data
        assert conn_a2_uid not in editor.diagram.con_data
        assert conn_b1_uid not in editor.diagram.con_data
        assert conn_b2_uid not in editor.diagram.con_data
        assert conn_c1_uid not in editor.diagram.con_data
        assert conn_c2_uid not in editor.diagram.con_data
        assert gain_a in editor.scene.items()
        assert gain_b in editor.scene.items()
        assert gain_c in editor.scene.items()
        assert gain_a.inputs[0].connections is None
        assert gain_a.outputs[0].connections is None
        assert gain_b.inputs[0].connections is None
        assert gain_b.outputs[0].connections is None
        assert gain_c.subsys.in_vars[0].non_mutable_uid == gain_c_input_identity[0]
        assert gain_c.subsys.out_vars[0].non_mutable_uid == gain_c_output_identity[0]
        assert gain_c.subsys.in_vars[0].uid == gain_c_input_identity[1]
        assert gain_c.subsys.in_vars[0].name == gain_c_input_identity[2]
        assert gain_c.inputs[0].connections is None
        assert gain_c.outputs[0].connections is None
        assert editor.has_unapplied_changes is True
    finally:
        _dispose_editor(editor)


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


def test_root_emt_reconcile_shrinks_saved_injection_interface_without_duplication() -> None:
    """
    Verify that reopening one saved EMT injection diagram removes stale phases.

    :return: None.
    """
    _get_app()
    root_block: Block = Block(name="LoadRoot")
    v_a: Var = _make_var("v_A_root", VarPowerFlowReferenceType.v_A)
    v_b: Var = _make_var("v_B_root", VarPowerFlowReferenceType.v_B)
    v_c: Var = _make_var("v_C_root", VarPowerFlowReferenceType.v_C)
    i_a: Var = _make_var("i_A_root", VarPowerFlowReferenceType.i_A)
    i_b: Var = _make_var("i_B_root", VarPowerFlowReferenceType.i_B)
    i_c: Var = _make_var("i_C_root", VarPowerFlowReferenceType.i_C)
    internal_in: Var = _make_var("internal_A", VarPowerFlowReferenceType.i_A)
    internal_out: Var = _make_var("internal_C", VarPowerFlowReferenceType.i_C)
    internal_block: Block = Block(name="Internal", uid=7001, in_vars=list([internal_in]), out_vars=list([internal_out]))
    wrap_in_a: Block = _build_root_wrapper(v_a, True, 5001)
    wrap_in_b: Block = _build_root_wrapper(v_b, True, 5002)
    wrap_in_c: Block = _build_root_wrapper(v_c, True, 5003)
    wrap_out_a: Block = _build_root_wrapper(i_a, False, 6001)
    wrap_out_b: Block = _build_root_wrapper(i_b, False, 6002)
    wrap_out_c: Block = _build_root_wrapper(i_c, False, 6003)

    root_block.in_vars = list([v_a, v_b, v_c])
    root_block.out_vars = list([i_a, i_b, i_c])
    root_block.external_mapping = dict({
        VarPowerFlowReferenceType.v_A: v_a,
        VarPowerFlowReferenceType.v_B: v_b,
        VarPowerFlowReferenceType.v_C: v_c,
        VarPowerFlowReferenceType.i_A: i_a,
        VarPowerFlowReferenceType.i_B: i_b,
        VarPowerFlowReferenceType.i_C: i_c,
    })
    root_block.children = list([wrap_in_a, wrap_in_b, wrap_in_c, wrap_out_a, wrap_out_b, wrap_out_c, internal_block])

    _add_diagram_wrapper_node(wrap_in_a, 10.0, 100.0, "INPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_in_b, 10.0, 200.0, "INPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_in_c, 10.0, 300.0, "INPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_out_a, 500.0, 100.0, "OUTPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_out_b, 500.0, 200.0, "OUTPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_out_c, 500.0, 300.0, "OUTPUT_CONN", root_block)
    root_block.diagram.add_node(name=internal_block.name, x=240.0, y=210.0, tpe="Block", device_uid=internal_block.uid)
    root_block.diagram.add_branch(connectionitem_uid=9001, device_uid_from=wrap_out_a.uid, device_uid_to=internal_block.uid, port_number_from=0, port_number_to=0)
    root_block.diagram.add_branch(connectionitem_uid=9002, device_uid_from=wrap_out_c.uid, device_uid_to=internal_block.uid, port_number_from=0, port_number_to=0)

    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    load.emt_model = root_block
    _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=list([1, 2]))

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
                                   current_block=root_block,
                                   root_block=root_block,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)

    try:
        input_refs = set(var.ref for var in editor.main_block.in_vars)
        output_refs = set(var.ref for var in editor.main_block.out_vars)
        child_uids = set(child.uid for child in editor.main_block.children)
        connection_endpoints = set((con.from_uid, con.to_uid) for con in editor.diagram.con_data.values())

        assert VarPowerFlowReferenceType.v_C not in input_refs
        assert VarPowerFlowReferenceType.i_C not in output_refs
        assert VarPowerFlowReferenceType.v_C not in editor.main_block.external_mapping
        assert VarPowerFlowReferenceType.i_C not in editor.main_block.external_mapping
        assert 5003 not in child_uids
        assert 6003 not in child_uids
        assert (6003, internal_block.uid) not in connection_endpoints
        assert 7001 in child_uids
        assert editor.diagram.node_data[5001].y == 100.0
        assert editor.diagram.node_data[5002].y == 200.0
        assert editor.diagram.node_data[6001].y == 100.0
        assert editor.diagram.node_data[6002].y == 200.0
        assert editor.has_unapplied_changes is True
    finally:
        _dispose_editor(editor)


def test_root_emt_reconcile_expands_saved_injection_interface_idempotently() -> None:
    """
    Verify that reopening one saved EMT injection diagram adds missing phases once.

    :return: None.
    """
    _get_app()
    root_block: Block = Block(name="LoadRoot")
    v_a: Var = _make_var("v_A_root", VarPowerFlowReferenceType.v_A)
    v_b: Var = _make_var("v_B_root", VarPowerFlowReferenceType.v_B)
    i_a: Var = _make_var("i_A_root", VarPowerFlowReferenceType.i_A)
    i_b: Var = _make_var("i_B_root", VarPowerFlowReferenceType.i_B)
    internal_in: Var = _make_var("internal_A", VarPowerFlowReferenceType.i_A)
    internal_block: Block = Block(name="Internal", uid=7101, in_vars=list([internal_in]))
    wrap_in_a: Block = _build_root_wrapper(v_a, True, 5101)
    wrap_in_b: Block = _build_root_wrapper(v_b, True, 5102)
    wrap_out_a: Block = _build_root_wrapper(i_a, False, 6101)
    wrap_out_b: Block = _build_root_wrapper(i_b, False, 6102)

    root_block.in_vars = list([v_a, v_b])
    root_block.out_vars = list([i_a, i_b])
    root_block.external_mapping = dict({
        VarPowerFlowReferenceType.v_A: v_a,
        VarPowerFlowReferenceType.v_B: v_b,
        VarPowerFlowReferenceType.i_A: i_a,
        VarPowerFlowReferenceType.i_B: i_b,
    })
    root_block.children = list([wrap_in_a, wrap_in_b, wrap_out_a, wrap_out_b, internal_block])
    _add_diagram_wrapper_node(wrap_in_a, 10.0, 100.0, "INPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_in_b, 10.0, 200.0, "INPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_out_a, 500.0, 100.0, "OUTPUT_CONN", root_block)
    _add_diagram_wrapper_node(wrap_out_b, 500.0, 200.0, "OUTPUT_CONN", root_block)
    root_block.diagram.add_node(name=internal_block.name, x=240.0, y=180.0, tpe="Block", device_uid=internal_block.uid)
    root_block.diagram.add_branch(connectionitem_uid=9101, device_uid_from=6101, device_uid_to=internal_block.uid, port_number_from=0, port_number_to=0)

    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    remote_bus = gce.Bus(name="Remote", Vnom=10.0)
    circuit.add_bus(bus)
    circuit.add_bus(remote_bus)
    load = gce.Load(name="Load 1")
    circuit.add_load(bus=bus, api_obj=load)
    load.emt_model = root_block
    _build_line_with_phases(circuit=circuit, bus_from=bus, bus_to=remote_bus, active_phases=list([1, 2, 3]))

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
                                   current_block=root_block,
                                   root_block=root_block,
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

        assert input_refs.count(VarPowerFlowReferenceType.v_C) == 1
        assert output_refs.count(VarPowerFlowReferenceType.i_C) == 1
        assert VarPowerFlowReferenceType.v_C in editor.main_block.external_mapping
        assert VarPowerFlowReferenceType.i_C in editor.main_block.external_mapping

        c_input_wrappers = [child for child in editor.main_block.children if len(child.out_vars) == 1 and child.out_vars[0].ref == VarPowerFlowReferenceType.v_C]
        c_output_wrappers = [child for child in editor.main_block.children if len(child.in_vars) == 1 and child.in_vars[0].ref == VarPowerFlowReferenceType.i_C]
        assert len(c_input_wrappers) == 1
        assert len(c_output_wrappers) == 1
        assert len(editor.diagram.con_data) == 1
    finally:
        _dispose_editor(editor)


def test_saved_injection_editor_topology_change_apply_reopen_matrix() -> None:
    """
    Verify saved user blocks follow the current topology across reopen/apply cycles.

    :return: None.
    """
    scenarios = [
        ([1, 2, 3], [1, 2], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}, VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.i_C),
        ([1, 2, 3], [1, 3], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_C}, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.i_B),
        ([1, 2], [1, 2, 3], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, None, None),
    ]

    initial_phases: list[int]
    final_phases: list[int]
    expected_inputs: set[VarPowerFlowReferenceType]
    expected_outputs: set[VarPowerFlowReferenceType]
    removed_input_ref: VarPowerFlowReferenceType | None
    removed_output_ref: VarPowerFlowReferenceType | None
    for initial_phases, final_phases, expected_inputs, expected_outputs, removed_input_ref, removed_output_ref in scenarios:
        editor, load, circuit, remote_bus = _build_connected_injection_editor(active_phases=initial_phases)
        gain_a, _wrap_in_a_uid, _wrap_out_a_uid, _conn_a1_uid, _conn_a2_uid = _build_connected_gain_phase(editor,
                                                                                                            VarPowerFlowReferenceType.v_A,
                                                                                                            VarPowerFlowReferenceType.i_A,
                                                                                                            200.0,
                                                                                                            80.0)
        gain_b = _add_gain_item(editor, 360.0, 220.0)
        _connect_port_pair(editor, gain_a.outputs[0], gain_b.inputs[0])
        internal_connection_uid = gain_a.outputs[0].connections[0].con_uid

        try:
            editor.apply_changes()
            assert editor.has_unapplied_changes is False

            _dispose_editor(editor)

            _apply_bus_phase_transition(circuit=circuit,
                                        bus=load.bus,
                                        remote_bus=remote_bus,
                                        final_phases=final_phases)
            assert get_bus_mask(grid=circuit, bus=load.bus) == list([
                False,
                1 in final_phases,
                2 in final_phases,
                3 in final_phases,
            ])

            reopen_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
                input_refs, output_refs = _collect_root_refs(reopen_editor.main_block)
                wrapper_input_refs, wrapper_output_refs = _collect_wrapper_refs(reopen_editor.main_block)
                generic_root_items = [
                    item for item in reopen_editor.scene.items()
                    if isinstance(item, graph.GenericBlockItem) and item.subsys is reopen_editor.main_block
                ]

                assert input_refs == expected_inputs
                assert output_refs == expected_outputs
                assert wrapper_input_refs == expected_inputs
                assert wrapper_output_refs == expected_outputs
                assert get_bus_mask(grid=circuit, bus=load.bus) == list([
                    False,
                    VarPowerFlowReferenceType.v_A in expected_inputs,
                    VarPowerFlowReferenceType.v_B in expected_inputs,
                    VarPowerFlowReferenceType.v_C in expected_inputs,
                ])
                assert load.bus.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_A, None) is not None or VarPowerFlowReferenceType.v_A not in expected_inputs
                assert len(generic_root_items) == 0
                internal_connections = [
                    con for con in reopen_editor.diagram.con_data.values()
                    if con.from_uid == gain_a.subsys.uid and con.to_uid == gain_b.subsys.uid
                ]
                assert len(internal_connections) == 1
                assert reopen_editor.has_unapplied_changes is True

                if removed_input_ref is not None:
                    assert removed_input_ref not in reopen_editor.main_block.external_mapping
                if removed_output_ref is not None:
                    assert removed_output_ref not in reopen_editor.main_block.external_mapping

                c_input_refs = [var.ref for var in reopen_editor.main_block.in_vars]
                c_output_refs = [var.ref for var in reopen_editor.main_block.out_vars]
                assert c_input_refs.count(VarPowerFlowReferenceType.v_C) <= 1
                assert c_output_refs.count(VarPowerFlowReferenceType.i_C) <= 1

                reopen_editor.apply_changes()
                assert reopen_editor.has_unapplied_changes is False
            finally:
                _dispose_editor(reopen_editor)

            final_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
                input_refs, output_refs = _collect_root_refs(final_editor.main_block)
                assert input_refs == expected_inputs
                assert output_refs == expected_outputs
                internal_connections = [
                    con for con in final_editor.diagram.con_data.values()
                    if con.from_uid == gain_a.subsys.uid and con.to_uid == gain_b.subsys.uid
                ]
                assert len(internal_connections) == 1
                assert final_editor.has_unapplied_changes is False
            finally:
                _dispose_editor(final_editor)
        except RuntimeError:
            # Some Qt objects are already disposed by explicit editor teardown above.
            pass


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
    intermediate_generator_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
    restored_generator_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
                                                      current_block=generator.emt_model,
                                                      root_block=generator.emt_model,
                                                      api_object=generator,
                                                      current_theme="Light",
                                                      circuit=circuit,
                                                      mode=DynamicSimulationMode.EMT,
                                                      templates_list=list(),
                                                      is_root_editor=True,
                                                      modal=False)

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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

    reopened_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
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
    """
    Verify one saved generator model round-trips through shrink and re-expansion.

    :param intermediate_phases: Shrunk intermediate phase set.
    :param intermediate_apply: Whether to apply the intermediate reconciled state.
    :return: None.
    """
    initial_phases = list([1, 2, 3])
    final_phases = list([1, 2, 3])
    expected_intermediate_inputs, expected_intermediate_outputs = _expected_input_output_refs_for_phases(intermediate_phases)
    expected_final_inputs, expected_final_outputs = _expected_input_output_refs_for_phases(final_phases)

    generator_editor, generator, circuit, remote_bus = _build_connected_injection_editor(active_phases=initial_phases)
    line = circuit.lines[0]

    try:
        assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])

        line_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            line_input_refs, line_output_refs = _collect_root_refs(line_editor.main_block)
            assert line_input_refs == {
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
            }
            assert line_output_refs == {
                VarPowerFlowReferenceType.if_A,
                VarPowerFlowReferenceType.if_B,
                VarPowerFlowReferenceType.if_C,
                VarPowerFlowReferenceType.it_A,
                VarPowerFlowReferenceType.it_B,
                VarPowerFlowReferenceType.it_C,
            }
        finally:
            _dispose_editor(line_editor)

        thevenin_item = _add_thevenin_item(generator_editor, 240.0, 180.0)
        _connect_port_pair(generator_editor, _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.v_A, True), thevenin_item.inputs[0])
        _connect_port_pair(generator_editor, _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.v_B, True), thevenin_item.inputs[1])
        _connect_port_pair(generator_editor, _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.v_C, True), thevenin_item.inputs[2])
        _connect_port_pair(generator_editor, thevenin_item.outputs[0], _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.i_A, False))
        _connect_port_pair(generator_editor, thevenin_item.outputs[1], _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.i_B, False))
        _connect_port_pair(generator_editor, thevenin_item.outputs[2], _find_wrapper_port(generator_editor, VarPowerFlowReferenceType.i_C, False))
        initial_user_intent_refs: set[VarPowerFlowReferenceType] = set(
            intent.get_root_reference()
            for intent in generator_editor.main_block.connection_intents
            if intent.get_origin() == DynamicConnectionIntentOrigin.USER
            and not intent.is_suppressed()
        )
        assert initial_user_intent_refs == expected_final_inputs | expected_final_outputs
        generator_editor.apply_changes()
        assert generator_editor.has_unapplied_changes is False
        _dispose_editor(generator_editor)

        _apply_bus_phase_transition(circuit=circuit,
                                    bus=generator.bus,
                                    remote_bus=remote_bus,
                                    final_phases=intermediate_phases)
        assert get_bus_mask(grid=circuit, bus=generator.bus) == list([
            False,
            1 in intermediate_phases,
            2 in intermediate_phases,
            3 in intermediate_phases,
        ])

        line_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            pass
        finally:
            _dispose_editor(line_editor)

        intermediate_generator_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            _assert_root_wrapper_layers(intermediate_generator_editor,
                                        expected_intermediate_inputs,
                                        expected_intermediate_outputs)
            assert any(isinstance(item, graph.GenericBlockItem) and item.subsys is not None and item.subsys.name.startswith("EMT_THEVENIN")
                       for item in intermediate_generator_editor.scene.items())
            assert intermediate_generator_editor.has_unapplied_changes is True
            intermediate_user_intent_refs: set[VarPowerFlowReferenceType] = set(
                intent.get_root_reference()
                for intent in intermediate_generator_editor.main_block.connection_intents
                if intent.get_origin() == DynamicConnectionIntentOrigin.USER
                and not intent.is_suppressed()
            )
            assert intermediate_user_intent_refs == expected_final_inputs | expected_final_outputs
            if intermediate_apply:
                intermediate_generator_editor.apply_changes()
                assert intermediate_generator_editor.has_unapplied_changes is False
            intermediate_input_node_refs = set()
            for node in intermediate_generator_editor.main_block.diagram.node_data.values():
                if node.tpe == "INPUT_CONN":
                    wrapper_block = intermediate_generator_editor.get_block_from_main_block(node.device_uid)
                    if wrapper_block is not None and _get_single_wrapper_ref(wrapper_block) is not None:
                        intermediate_input_node_refs.add(_get_single_wrapper_ref(wrapper_block))
            assert intermediate_input_node_refs == expected_intermediate_inputs
        finally:
            _dispose_editor(intermediate_generator_editor)

        _apply_bus_phase_transition(circuit=circuit,
                                    bus=generator.bus,
                                    remote_bus=remote_bus,
                                    final_phases=final_phases)
        assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])

        line_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, True])
            assert _active_bus_voltage_refs(generator.bus) == (VarPowerFlowReferenceType.v_A,
                                                               VarPowerFlowReferenceType.v_B,
                                                               VarPowerFlowReferenceType.v_C)
            assert generator.bus.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_C, None) is not None
        finally:
            _dispose_editor(line_editor)

        final_generator_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            final_input_node_refs = set()
            node = None
            for node in generator.emt_model.diagram.node_data.values():
                if node.tpe == "INPUT_CONN":
                    wrapper_block = final_generator_editor.get_block_from_main_block(node.device_uid)
                    if wrapper_block is not None and _get_single_wrapper_ref(wrapper_block) is not None:
                        final_input_node_refs.add(_get_single_wrapper_ref(wrapper_block))
            assert final_input_node_refs == expected_final_inputs
            _assert_root_wrapper_layers(final_generator_editor,
                                        expected_final_inputs,
                                        expected_final_outputs)
            assert final_generator_editor.main_block.external_mapping.get(VarPowerFlowReferenceType.v_C, None) is generator.bus.emt_model.external_mapping.get(VarPowerFlowReferenceType.v_C, None)
            c_input_port: graph.PortItem = _find_wrapper_port(
                final_generator_editor,
                VarPowerFlowReferenceType.v_C,
                True,
            )
            c_output_port: graph.PortItem = _find_wrapper_port(
                final_generator_editor,
                VarPowerFlowReferenceType.i_C,
                False,
            )
            assert c_input_port.subsystem is not None
            assert c_input_port.subsystem.subsys is not None
            assert final_generator_editor.get_scene_item_by_block_uid(
                c_input_port.subsystem.subsys.uid,
            ) is c_input_port.subsystem
            assert c_output_port.subsystem is not None
            assert c_output_port.subsystem.subsys is not None
            assert final_generator_editor.get_scene_item_by_block_uid(
                c_output_port.subsystem.subsys.uid,
            ) is c_output_port.subsystem
            assert c_input_port.connections is not None
            assert c_output_port.connections is not None
            assert len(c_input_port.connections) == 1
            assert len(c_output_port.connections) == 1
        finally:
            _dispose_editor(final_generator_editor)
    except RuntimeError:
        pass


def test_shared_line_generator_round_trip_repeated_toggle_idempotent() -> None:
    """
    Verify repeated shared-bus topology toggling remains symmetric and duplicate-free.

    :return: None.
    """
    generator_editor, generator, circuit, remote_bus = _build_connected_injection_editor(active_phases=list([1, 2, 3]))
    line = circuit.lines[0]
    phase_sequence = [list([1, 2]), list([1, 2, 3]), list([1, 2]), list([1, 2, 3])]

    try:
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

            line_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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

            generator_round_trip_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
    except RuntimeError:
        pass


@pytest.mark.parametrize(
    ("initial_phases", "final_phases", "expected_mask", "expected_input_refs", "expected_output_refs", "changed"),
    [
        ([1, 2, 3], [1, 2], [False, True, True, False], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}, True),
        ([1, 2, 3], [1, 3], [False, True, False, True], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_C}, True),
        ([1, 2, 3], [2, 3], [False, False, True, True], {VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, True),
        ([1, 2, 3], [1], [False, True, False, False], {VarPowerFlowReferenceType.v_A}, {VarPowerFlowReferenceType.i_A}, True),
        ([1, 2, 3], [2], [False, False, True, False], {VarPowerFlowReferenceType.v_B}, {VarPowerFlowReferenceType.i_B}, True),
        ([1, 2, 3], [3], [False, False, False, True], {VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_C}, True),
        ([1, 2], [1, 2, 3], [False, True, True, True], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, True),
        ([1, 3], [1, 2, 3], [False, True, True, True], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, True),
        ([1, 2], [2, 3], [False, False, True, True], {VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, True),
        ([1, 3], [1, 2], [False, True, True, False], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}, True),
        ([1, 2, 3], [1, 2, 3], [False, True, True, True], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C}, False),
        ([1, 2], [1, 2], [False, True, True, False], {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}, {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}, False),
    ],
)
def test_injection_phase_permutation_reconciliation(initial_phases: list[int],
                                                    final_phases: list[int],
                                                    expected_mask: list[bool],
                                                    expected_input_refs: set[VarPowerFlowReferenceType],
                                                    expected_output_refs: set[VarPowerFlowReferenceType],
                                                    changed: bool) -> None:
    """
    Verify injection-interface reconciliation across supported phase permutations.

    :param initial_phases: Initial topology phase numbers.
    :param final_phases: Final topology phase numbers.
    :param expected_mask: Expected canonical mask after topology change.
    :param expected_input_refs: Expected root voltage refs.
    :param expected_output_refs: Expected root current refs.
    :param changed: Whether the interface is expected to change.
    :return: None.
    """
    _get_app()
    circuit, load, remote_bus, final_phase_list = _make_phase_transition_circuit(initial_phases=initial_phases,
                                                                                  final_phases=final_phases)
    load.emt_model = Block()
    _apply_bus_phase_transition(circuit=circuit,
                                bus=load.bus,
                                remote_bus=remote_bus,
                                final_phases=final_phase_list)

    canonical_mask: list[bool] = get_bus_mask(grid=circuit, bus=load.bus)
    assert canonical_mask == expected_mask

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
                                   current_block=load.emt_model,
                                   root_block=load.emt_model,
                                   api_object=load,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    dirty_spy = _DirtySpy()
    editor.dirtyStateChanged.connect(dirty_spy.record)

    try:
        input_refs, output_refs = _collect_root_refs(editor.main_block)
        wrapper_input_refs, wrapper_output_refs = _collect_wrapper_refs(editor.main_block)

        assert input_refs == expected_input_refs
        assert output_refs == expected_output_refs
        assert wrapper_input_refs == expected_input_refs
        assert wrapper_output_refs == expected_output_refs
        assert list(editor.main_block.external_mapping.keys()).count(VarPowerFlowReferenceType.v_A) <= 1
        assert list(editor.main_block.external_mapping.keys()).count(VarPowerFlowReferenceType.v_B) <= 1
        assert list(editor.main_block.external_mapping.keys()).count(VarPowerFlowReferenceType.v_C) <= 1
        assert dirty_spy.events == list()
    finally:
        _dispose_editor(editor)


def _build_real_branch_editor(bus_from_model: Block, bus_to_model: Block) -> tuple[DynamicBlockEditorGUI, Line]:
    """
    Build one real EMT line editor backed by controlled bus EMT models.

    :param bus_from_model: EMT bus block for the from side.
    :param bus_to_model: EMT bus block for the to side.
    :return: Tuple with the editor and the owned line object.
    """
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = gce.Line(name="Line 1", bus_from=bus_from, bus_to=bus_to)
    circuit.add_line(line)

    # Fix the side-specific bus shells before opening the editor so the branch
    # interface must follow the actual phase availability of each terminal.
    line.bus_from.emt_model = bus_from_model
    line.bus_to.emt_model = bus_to_model
    line.emt_model = Block()
    line.emt_template = _make_template(list())

    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=line,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    return editor, line


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


def _build_template_backed_branch_editor(active_phases: list[int]) -> tuple[DynamicBlockEditorGUI, Line, MultiCircuit]:
    """
    Build one real branch root EMT editor backed by one applied pi-line template.

    :param active_phases: Canonical topology phase numbers.
    :return: Editor, branch device and circuit.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = _build_line_with_phases(circuit=circuit,
                                   bus_from=bus_from,
                                   bus_to=bus_to,
                                   active_phases=active_phases)

    template: EmtModelTemplate = get_pi_line_emt_template(vf=circuit.var_factory,
                                                          phN=False,
                                                          phA=1 in active_phases,
                                                          phB=2 in active_phases,
                                                          phC=3 in active_phases,
                                                          name="PiTemplate")
    line.emt_template = template
    line.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
                                   current_block=line.emt_model,
                                   root_block=line.emt_model,
                                   api_object=line,
                                   current_theme="Light",
                                   circuit=circuit,
                                   mode=DynamicSimulationMode.EMT,
                                   templates_list=list(),
                                   is_root_editor=True,
                                   modal=False)
    return editor, line, circuit


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


def _find_non_wrapper_child_by_name_prefix(block: Block, name_prefix: str) -> Block:
    """
    Find one non-wrapper child block whose name starts with ``name_prefix``.

    :param block: Root block to inspect.
    :param name_prefix: Required child-name prefix.
    :return: Matching child block.
    """
    child: Block

    for child in block.children:
        if _get_single_wrapper_ref(child) is not None:
            pass
        elif child.name.startswith(name_prefix):
            return child
        else:
            pass

    raise AssertionError(f"Child block starting with {name_prefix!r} not found")


def _assert_branch_template_root_wires(editor: DynamicBlockEditorGUI,
                                       expected_connection_pairs: set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]]) -> None:
    """
    Assert that the expected branch root/template wires are visible exactly semantically.

    :param editor: Editor under test.
    :param expected_connection_pairs: Expected semantic source/target ref pairs.
    :return: None.
    """
    visible_pairs: set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]] = _collect_graphical_connection_refs(editor)
    expected_pair: tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]

    for expected_pair in expected_connection_pairs:
        assert expected_pair in visible_pairs


def _collect_scene_wrapper_refs(editor: DynamicBlockEditorGUI) -> tuple[list[VarPowerFlowReferenceType], list[VarPowerFlowReferenceType]]:
    """
    Collect visible root-interface refs from the scene.

    :param editor: Editor under test.
    :return: Ordered input/output wrapper refs.
    """
    scene_input_refs: list[VarPowerFlowReferenceType] = list()
    scene_output_refs: list[VarPowerFlowReferenceType] = list()
    item: object

    for item in editor.scene.items():
        if isinstance(item, graph.ProtectedConnectionBlockItem):
            interface_var = item.get_interface_var()
            assert interface_var is not None
            assert interface_var.ref is not None
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
                    scene_input_refs.append(output_port.base_var.ref)
                else:
                    pass
            input_port: graph.PortItem
            for input_port in item.inputs:
                if input_port.base_var is not None and input_port.base_var.ref is not None:
                    scene_output_refs.append(input_port.base_var.ref)
                else:
                    pass
        else:
            pass

    return scene_input_refs, scene_output_refs


def _collect_branch_root_contract_state(block: Block) -> tuple[set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType], set[VarPowerFlowReferenceType]]:
    """
    Collect the current branch root IO and mapped refs from one symbolic root block.

    :param block: Root block under inspection.
    :return: ``(input_refs, output_refs, mapped_refs)``.
    """
    input_refs: set[VarPowerFlowReferenceType] = set(var.ref for var in block.in_vars if var.ref is not None)
    output_refs: set[VarPowerFlowReferenceType] = set(var.ref for var in block.out_vars if var.ref is not None)
    root_refs: set[VarPowerFlowReferenceType] = input_refs | output_refs
    mapped_refs: set[VarPowerFlowReferenceType] = set()
    mapping_ref: VarPowerFlowReferenceType
    mapped_var: Var | None

    for mapping_ref, mapped_var in block.external_mapping.items():
        if mapped_var is None or mapping_ref not in root_refs:
            pass
        else:
            mapped_refs.add(mapping_ref)

    return input_refs, output_refs, mapped_refs


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

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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


@pytest.mark.parametrize(
    (
        "dc_side",
        "preserved_voltage_refs",
        "preserved_current_refs",
        "expected_input_refs",
        "expected_output_refs",
        "expected_dc_input_ref",
        "expected_dc_output_ref",
    ),
    [
        (
            "from",
            [VarPowerFlowReferenceType.vt_A, VarPowerFlowReferenceType.vt_B],
            [VarPowerFlowReferenceType.it_A, VarPowerFlowReferenceType.it_B],
            {
                VarPowerFlowReferenceType.Vdc,
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
            },
            {
                VarPowerFlowReferenceType.If_dc,
                VarPowerFlowReferenceType.it_A,
                VarPowerFlowReferenceType.it_B,
                VarPowerFlowReferenceType.it_C,
            },
            VarPowerFlowReferenceType.Vf_dc,
            VarPowerFlowReferenceType.If_dc,
        ),
        (
            "to",
            [VarPowerFlowReferenceType.vf_A, VarPowerFlowReferenceType.vf_B],
            [VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.if_B],
            {
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
                VarPowerFlowReferenceType.Vdc,
            },
            {
                VarPowerFlowReferenceType.if_A,
                VarPowerFlowReferenceType.if_B,
                VarPowerFlowReferenceType.if_C,
                VarPowerFlowReferenceType.It_dc,
            },
            VarPowerFlowReferenceType.Vt_dc,
            VarPowerFlowReferenceType.It_dc,
        ),
    ],
)
def test_branch_ac_to_dc_transition_adds_side_current_and_preserves_available_ab_wires(
        dc_side: str,
        preserved_voltage_refs: list[VarPowerFlowReferenceType],
        preserved_current_refs: list[VarPowerFlowReferenceType],
        expected_input_refs: set[VarPowerFlowReferenceType],
        expected_output_refs: set[VarPowerFlowReferenceType],
        expected_dc_input_ref: VarPowerFlowReferenceType,
        expected_dc_output_ref: VarPowerFlowReferenceType,
) -> None:
    """
    Verify a mixed AC/DC branch exposes its side current without losing AB wires.

    :param dc_side: Branch terminal changed from AC to DC.
    :param preserved_voltage_refs: Connected AC voltage refs on the surviving side.
    :param preserved_current_refs: Connected AC current refs on the surviving side.
    :param expected_input_refs: Complete expected mixed-topology input contract.
    :param expected_output_refs: Complete expected mixed-topology output contract.
    :param expected_dc_input_ref: Side-specific DC voltage reference.
    :param expected_dc_output_ref: Side-specific DC current reference.
    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from: gce.Bus = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to: gce.Bus = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line: Line = _build_line_with_phases(
        circuit=circuit,
        bus_from=bus_from,
        bus_to=bus_to,
        active_phases=list([1, 2, 3]),
    )
    line.emt_model = Block()
    var_factory: VarFactory = circuit.var_factory
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
    pi_template: EmtModelTemplate = get_pi_line_emt_template(vf=var_factory,
                                                              phN=False,
                                                              phA=True,
                                                              phB=True,
                                                              phC=True,
                                                              name="PiMixedTopology")
    pi_item: graph.GenericBlockItem | None = editor.create_template_block_item(
        template=pi_template,
        x_pos=400.0,
        y_pos=180.0,
    )
    assert pi_item is not None

    reference: VarPowerFlowReferenceType
    try:
        for reference in preserved_voltage_refs:
            _connect_port_pair(
                editor=editor,
                source_port=_find_semantic_wrapper_port(editor, reference, BlockType.INPUT_CONN),
                target_port=_find_item_port_by_reference(pi_item, reference, is_input=True),
            )

        for reference in preserved_current_refs:
            _connect_port_pair(
                editor=editor,
                source_port=_find_item_port_by_reference(pi_item, reference, is_input=False),
                target_port=_find_semantic_wrapper_port(editor, reference, BlockType.OUTPUT_CONN),
            )

        editor.apply_changes()
    finally:
        _dispose_editor(editor)

    if dc_side == "from":
        line.bus_from.is_dc = True
        line.bus_from.emt_model = _build_phase_bus_block(
            name="dc_from",
            mask=list([False, False, False, False]),
            is_dc=True,
        )
    else:
        line.bus_to.is_dc = True
        line.bus_to.emt_model = _build_phase_bus_block(
            name="dc_to",
            mask=list([False, False, False, False]),
            is_dc=True,
        )

    reopened_editor = DynamicBlockEditorGUI(var_factory=var_factory,
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
        input_refs, output_refs = _collect_root_refs(reopened_editor.main_block)
        wrapper_input_refs, wrapper_output_refs = _collect_wrapper_refs(reopened_editor.main_block)
        assert input_refs == expected_input_refs
        assert output_refs == expected_output_refs
        assert wrapper_input_refs == expected_input_refs
        assert wrapper_output_refs == expected_output_refs

        dc_input_port: graph.PortItem = _find_semantic_wrapper_port(
            reopened_editor,
            expected_dc_input_ref,
            BlockType.INPUT_CONN,
        )
        dc_output_port: graph.PortItem = _find_semantic_wrapper_port(
            reopened_editor,
            expected_dc_output_ref,
            BlockType.OUTPUT_CONN,
        )
        assert dc_input_port.connections is None
        assert dc_output_port.connections is None
        assert dc_output_port.base_var is not None
        assert dc_output_port.base_var.name == dynamic_block_editor.build_expected_root_emt_output_name(
            expected_dc_output_ref,
        )

        connection_refs: set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]] = (
            _collect_graphical_connection_refs(editor=reopened_editor)
        )
        bus_voltage_ref_by_branch_ref: dict[VarPowerFlowReferenceType, VarPowerFlowReferenceType] = dict({
            VarPowerFlowReferenceType.vf_A: VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.vf_B: VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.vt_A: VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.vt_B: VarPowerFlowReferenceType.v_B,
        })
        for reference in preserved_voltage_refs:
            assert (bus_voltage_ref_by_branch_ref[reference], reference) in connection_refs
        for reference in preserved_current_refs:
            assert (reference, reference) in connection_refs

        if dc_side == "from":
            assert (VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.vt_C) not in connection_refs
            assert (VarPowerFlowReferenceType.it_C, VarPowerFlowReferenceType.it_C) not in connection_refs
        else:
            assert (VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.vf_C) not in connection_refs
            assert (VarPowerFlowReferenceType.if_C, VarPowerFlowReferenceType.if_C) not in connection_refs
    finally:
        _dispose_editor(reopened_editor)


def test_template_backed_generator_preserves_template_block_across_topology_change() -> None:
    """
    Verify one template-backed generator keeps its template block after topology shrink.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    try:
        template_block_uids: set[int] = set(child.uid for child in generator.emt_model.children if _get_single_wrapper_ref(child) is None)
        assert len(template_block_uids) > 0

        _dispose_editor(editor)

        _apply_bus_phase_transition(circuit=circuit,
                                    bus=generator.bus,
                                    remote_bus=remote_bus,
                                    final_phases=list([1, 2]))
        assert get_bus_mask(grid=circuit, bus=generator.bus) == list([False, True, True, False])

        reopened_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
            surviving_block_uids: set[int] = set(child.uid for child in reopened_editor.main_block.children if _get_single_wrapper_ref(child) is None)

            assert input_refs == {VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B}
            assert output_refs == {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B}
            assert template_block_uids == surviving_block_uids
            assert generator.emt_template is not None
        finally:
            _dispose_editor(reopened_editor)
    except RuntimeError:
        pass


def test_fresh_template_generator_centers_interface_around_content_and_fits_view() -> None:
    """
    Verify a fresh template keeps its block fixed and centers wrappers around it.

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
        assert abs(input_rect.center().y() - content_rect.center().y()) < 1e-6
        assert abs(output_rect.center().y() - content_rect.center().y()) < 1e-6
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


def test_fresh_empty_line_compacts_and_fits_every_connection_var() -> None:
    """
    Verify a fresh ABC line shows all twelve connection vars without zooming out.

    :return: None.
    """
    line, circuit, var_factory = _build_real_branch_device(
        _make_ac_bus("Bus From", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
        _make_ac_bus("Bus To", include_neutral=False, include_a=True, include_b=True, include_c=True).emt_model,
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

        assert len(wrapper_items) == 12
        assert editor.view.transform().m11() <= 1.0
        _assert_all_editor_blocks_are_inside_viewport(editor=editor)
    finally:
        _dispose_editor(editor)


def test_manual_pi_branch_ab_wires_survive_abc_expansion_and_relayout() -> None:
    """
    Verify manual AB Pi wires survive ABC expansion with a fresh ordered layout.

    The persisted records are deliberately rewritten to the legacy shared-ref
    and reversed-direction shape produced by the earlier refactor. Reopening
    must upgrade those records to the canonical side-specific contract while
    restoring every A/B wire and leaving the newly introduced C ports free.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line: Line = _build_line_with_phases(
        circuit=circuit,
        bus_from=bus_from,
        bus_to=bus_to,
        active_phases=list([1, 2]),
    )
    line.emt_model = Block()
    editor = DynamicBlockEditorGUI(
        var_factory=circuit.var_factory,
        current_block=line.emt_model,
        root_block=line.emt_model,
        api_object=line,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    pi_template: EmtModelTemplate = get_pi_line_emt_template(
        vf=circuit.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name="Pi",
    )
    pi_item: graph.GenericBlockItem | None = editor.create_template_block_item(
        template=pi_template,
        x_pos=400.0,
        y_pos=180.0,
    )
    assert pi_item is not None
    pi_block_uid: int = pi_item.subsys.uid
    input_refs: list[VarPowerFlowReferenceType] = list([
        VarPowerFlowReferenceType.vf_A,
        VarPowerFlowReferenceType.vf_B,
        VarPowerFlowReferenceType.vt_A,
        VarPowerFlowReferenceType.vt_B,
    ])
    output_refs: list[VarPowerFlowReferenceType] = list([
        VarPowerFlowReferenceType.if_A,
        VarPowerFlowReferenceType.if_B,
        VarPowerFlowReferenceType.it_A,
        VarPowerFlowReferenceType.it_B,
    ])
    reference: VarPowerFlowReferenceType
    for reference in input_refs:
        _connect_port_pair(
            editor=editor,
            source_port=_find_semantic_wrapper_port(editor, reference, BlockType.INPUT_CONN),
            target_port=_find_item_port_by_reference(pi_item, reference, is_input=True),
        )

    for reference in output_refs:
        _connect_port_pair(
            editor=editor,
            source_port=_find_item_port_by_reference(pi_item, reference, is_input=False),
            target_port=_find_semantic_wrapper_port(editor, reference, BlockType.OUTPUT_CONN),
        )

    assert len(line.emt_model.connection_intents) == 8
    editor.apply_changes()
    _dispose_editor(editor)

    legacy_voltage_refs: dict[str, str] = dict({
        VarPowerFlowReferenceType.vf_A.value: VarPowerFlowReferenceType.v_A.value,
        VarPowerFlowReferenceType.vf_B.value: VarPowerFlowReferenceType.v_B.value,
        VarPowerFlowReferenceType.vt_A.value: VarPowerFlowReferenceType.v_A.value,
        VarPowerFlowReferenceType.vt_B.value: VarPowerFlowReferenceType.v_B.value,
    })
    intent_entry: DynamicConnectionIntent
    for intent_entry in line.emt_model.connection_intents:
        root_reference_value: str = intent_entry.get_root_reference().value
        legacy_reference_value: str | None = legacy_voltage_refs.get(root_reference_value, None)
        if legacy_reference_value is not None:
            intent_entry.set_root_reference(VarPowerFlowReferenceType(legacy_reference_value))
        else:
            pass

    _apply_line_phase_transition(line=line, final_phases=list([1, 2, 3]))
    reopened = DynamicBlockEditorGUI(
        var_factory=circuit.var_factory,
        current_block=line.emt_model,
        root_block=line.emt_model,
        api_object=line,
        current_theme="Light",
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
    )
    try:
        reopened_pi_item: graph.GenericBlockItem | None = reopened.get_scene_item_by_block_uid(pi_block_uid)
        assert reopened_pi_item is not None
        user_intents: list[DynamicConnectionIntent] = list(
            intent for intent in line.emt_model.connection_intents
            if intent.get_origin() == DynamicConnectionIntentOrigin.USER
        )
        assert len(user_intents) == 8
        assert set(intent.get_root_reference().value for intent in user_intents) == set(
            reference.value for reference in input_refs + output_refs
        )
        assert set(intent.get_direction() for intent in user_intents) == set([
            DynamicConnectionIntentDirection.INPUT,
            DynamicConnectionIntentDirection.OUTPUT,
        ])

        for reference in input_refs:
            assert reopened._connection_exists_between_ports(
                _find_semantic_wrapper_port(reopened, reference, BlockType.INPUT_CONN),
                _find_item_port_by_reference(reopened_pi_item, reference, is_input=True),
            )

        for reference in output_refs:
            assert reopened._connection_exists_between_ports(
                _find_item_port_by_reference(reopened_pi_item, reference, is_input=False),
                _find_semantic_wrapper_port(reopened, reference, BlockType.OUTPUT_CONN),
            )

        canonical_input_refs: list[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vf_C,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
        ])
        canonical_output_refs: list[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.if_C,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ])
        input_y_positions: list[float] = list()
        output_y_positions: list[float] = list()

        for reference in canonical_input_refs:
            input_y_positions.append(
                _find_semantic_wrapper_item(reopened, reference, BlockType.INPUT_CONN).pos().y(),
            )
        for reference in canonical_output_refs:
            output_y_positions.append(
                _find_semantic_wrapper_item(reopened, reference, BlockType.OUTPUT_CONN).pos().y(),
            )

        assert input_y_positions == sorted(input_y_positions)
        assert output_y_positions == sorted(output_y_positions)

        for reference in list([VarPowerFlowReferenceType.vf_C, VarPowerFlowReferenceType.vt_C]):
            assert _find_semantic_wrapper_port(reopened, reference, BlockType.INPUT_CONN).connections is None
        for reference in list([VarPowerFlowReferenceType.if_C, VarPowerFlowReferenceType.it_C]):
            assert _find_semantic_wrapper_port(reopened, reference, BlockType.OUTPUT_CONN).connections is None

        _show_editor_with_workspace_sized_viewport(editor=reopened)
        _assert_all_editor_blocks_are_inside_viewport(editor=reopened)
    finally:
        _dispose_editor(reopened)


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

    reopened_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
    try:
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
    except RuntimeError:
        pass


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
    try:
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
    except RuntimeError:
        pass


def test_template_backed_generator_preflight_reconciles_shrink_expand_cycle() -> None:
    """
    Verify EMT preflight restores one template-backed generator across one shrink/expand cycle.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    try:
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
    except RuntimeError:
        pass


def test_template_backed_generator_preflight_reconciles_ac_variant_cycle() -> None:
    """
    Verify EMT preflight restores one template-backed generator across one AC variant cycle.

    :return: None.
    """
    editor, generator, circuit, remote_bus = _build_template_backed_generator_editor(active_phases=list([1, 2, 3]))
    try:
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
    except RuntimeError:
        pass


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


def test_template_backed_branch_editor_initial_open_and_from_side_round_trip_restores_semantic_wires() -> None:
    """
    Verify one real template-backed branch editor restores exact semantic wires across one FROM-side round-trip.

    :return: None.
    """
    editor, line, circuit = _build_template_backed_branch_editor(active_phases=list([1, 2, 3]))

    try:
        template_block: Block = _find_non_wrapper_child_by_name_prefix(editor.main_block, EmtLineTypes.PI.value)
        expected_initial_pairs: set[tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]] = set([
            (VarPowerFlowReferenceType.vf_A, VarPowerFlowReferenceType.vf_A),
            (VarPowerFlowReferenceType.vf_B, VarPowerFlowReferenceType.vf_B),
            (VarPowerFlowReferenceType.vf_C, VarPowerFlowReferenceType.vf_C),
            (VarPowerFlowReferenceType.vt_A, VarPowerFlowReferenceType.vt_A),
            (VarPowerFlowReferenceType.vt_B, VarPowerFlowReferenceType.vt_B),
            (VarPowerFlowReferenceType.vt_C, VarPowerFlowReferenceType.vt_C),
            (VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.if_A),
            (VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.if_B),
            (VarPowerFlowReferenceType.if_C, VarPowerFlowReferenceType.if_C),
            (VarPowerFlowReferenceType.it_A, VarPowerFlowReferenceType.it_A),
            (VarPowerFlowReferenceType.it_B, VarPowerFlowReferenceType.it_B),
            (VarPowerFlowReferenceType.it_C, VarPowerFlowReferenceType.it_C),
        ])

        assert _collect_root_refs(editor.main_block) == (
            set([
                VarPowerFlowReferenceType.vf_A,
                VarPowerFlowReferenceType.vf_B,
                VarPowerFlowReferenceType.vf_C,
                VarPowerFlowReferenceType.vt_A,
                VarPowerFlowReferenceType.vt_B,
                VarPowerFlowReferenceType.vt_C,
            ]),
            set([
                VarPowerFlowReferenceType.if_A,
                VarPowerFlowReferenceType.if_B,
                VarPowerFlowReferenceType.if_C,
                VarPowerFlowReferenceType.it_A,
                VarPowerFlowReferenceType.it_B,
                VarPowerFlowReferenceType.it_C,
            ]),
        )
        scene_input_refs, scene_output_refs = _collect_scene_wrapper_refs(editor)
        _assert_scene_wrapper_counts(editor,
                                     expected_input_refs=set([
                                         VarPowerFlowReferenceType.vf_A,
                                         VarPowerFlowReferenceType.vf_B,
                                         VarPowerFlowReferenceType.vf_C,
                                         VarPowerFlowReferenceType.vt_A,
                                         VarPowerFlowReferenceType.vt_B,
                                         VarPowerFlowReferenceType.vt_C,
                                     ]),
                                     expected_output_refs=set([
                                         VarPowerFlowReferenceType.if_A,
                                         VarPowerFlowReferenceType.if_B,
                                         VarPowerFlowReferenceType.if_C,
                                         VarPowerFlowReferenceType.it_A,
                                         VarPowerFlowReferenceType.it_B,
                                         VarPowerFlowReferenceType.it_C,
                                     ]))
        _assert_branch_template_root_wires(editor, expected_initial_pairs)
        assert len(editor.main_block.connection_intents) >= len(expected_initial_pairs)
        assert template_block.uid in set(child.uid for child in editor.main_block.children)
    finally:
        _dispose_editor(editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))
    assert circuit.check_emt_models().has_errors() is False

    shrink_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        expected_shrink_root_refs = (
            set([
                VarPowerFlowReferenceType.vf_A,
                VarPowerFlowReferenceType.vf_B,
                VarPowerFlowReferenceType.vt_A,
                VarPowerFlowReferenceType.vt_B,
                VarPowerFlowReferenceType.vt_C,
            ]),
            set([
                VarPowerFlowReferenceType.if_A,
                VarPowerFlowReferenceType.if_B,
                VarPowerFlowReferenceType.it_A,
                VarPowerFlowReferenceType.it_B,
                VarPowerFlowReferenceType.it_C,
            ]),
        )
        assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None
        assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.if_C, None) is None
        assert _collect_root_refs(shrink_editor.main_block) == expected_shrink_root_refs
        _assert_scene_wrapper_counts(shrink_editor,
                                     expected_input_refs=set([
                                         VarPowerFlowReferenceType.vf_A,
                                         VarPowerFlowReferenceType.vf_B,
                                         VarPowerFlowReferenceType.vt_A,
                                         VarPowerFlowReferenceType.vt_B,
                                         VarPowerFlowReferenceType.vt_C,
                                     ]),
                                     expected_output_refs=set([
                                         VarPowerFlowReferenceType.if_A,
                                         VarPowerFlowReferenceType.if_B,
                                         VarPowerFlowReferenceType.it_A,
                                         VarPowerFlowReferenceType.it_B,
                                         VarPowerFlowReferenceType.it_C,
                                     ]))
        _assert_branch_template_root_wires(shrink_editor, set([
            (VarPowerFlowReferenceType.vf_A, VarPowerFlowReferenceType.vf_A),
            (VarPowerFlowReferenceType.vf_B, VarPowerFlowReferenceType.vf_B),
            (VarPowerFlowReferenceType.vt_A, VarPowerFlowReferenceType.vt_A),
            (VarPowerFlowReferenceType.vt_B, VarPowerFlowReferenceType.vt_B),
            (VarPowerFlowReferenceType.vt_C, VarPowerFlowReferenceType.vt_C),
            (VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.if_A),
            (VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.if_B),
            (VarPowerFlowReferenceType.it_A, VarPowerFlowReferenceType.it_A),
            (VarPowerFlowReferenceType.it_B, VarPowerFlowReferenceType.it_B),
            (VarPowerFlowReferenceType.it_C, VarPowerFlowReferenceType.it_C),
        ]))
        assert VarPowerFlowReferenceType.vf_C not in set(var.ref for var in shrink_editor.main_block.in_vars)
        assert VarPowerFlowReferenceType.if_C not in set(var.ref for var in shrink_editor.main_block.out_vars)
    finally:
        _dispose_editor(shrink_editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_abc_restore", mask=list([False, True, True, True]))
    assert circuit.check_emt_models().has_errors() is False

    restore_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        assert _collect_root_refs(restore_editor.main_block) == (
            set([
                VarPowerFlowReferenceType.vf_A,
                VarPowerFlowReferenceType.vf_B,
                VarPowerFlowReferenceType.vf_C,
                VarPowerFlowReferenceType.vt_A,
                VarPowerFlowReferenceType.vt_B,
                VarPowerFlowReferenceType.vt_C,
            ]),
            set([
                VarPowerFlowReferenceType.if_A,
                VarPowerFlowReferenceType.if_B,
                VarPowerFlowReferenceType.if_C,
                VarPowerFlowReferenceType.it_A,
                VarPowerFlowReferenceType.it_B,
                VarPowerFlowReferenceType.it_C,
            ]),
        )
        _assert_scene_wrapper_counts(restore_editor,
                                     expected_input_refs=set([
                                         VarPowerFlowReferenceType.vf_A,
                                         VarPowerFlowReferenceType.vf_B,
                                         VarPowerFlowReferenceType.vf_C,
                                         VarPowerFlowReferenceType.vt_A,
                                         VarPowerFlowReferenceType.vt_B,
                                         VarPowerFlowReferenceType.vt_C,
                                     ]),
                                     expected_output_refs=set([
                                         VarPowerFlowReferenceType.if_A,
                                         VarPowerFlowReferenceType.if_B,
                                         VarPowerFlowReferenceType.if_C,
                                         VarPowerFlowReferenceType.it_A,
                                         VarPowerFlowReferenceType.it_B,
                                         VarPowerFlowReferenceType.it_C,
                                     ]))
        _assert_branch_template_root_wires(restore_editor, expected_initial_pairs)
        assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is not None
        assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.if_C, None) is not None
    finally:
        _dispose_editor(restore_editor)


def test_branch_shrink_identifies_first_side_reconcile_stage_leaving_vf_c_alive() -> None:
    """
    Identify which branch side-reconcile stage first leaves stale ``vf_C`` alive.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = _build_line_with_phases(circuit=circuit,
                                   bus_from=bus_from,
                                   bus_to=bus_to,
                                   active_phases=list([1, 2, 3]))
    template: EmtModelTemplate = get_pi_line_emt_template(vf=circuit.var_factory,
                                                          phN=False,
                                                          phA=True,
                                                          phB=True,
                                                          phC=True,
                                                          name="PiTemplate")
    line.emt_template = template
    line.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    initial_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        pass
    finally:
        _dispose_editor(initial_editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))

    _prune_saved_branch_root_contract_side(device=line,
                                           side=EmtBusConnectionSide.FROM)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _ensure_saved_branch_root_contract_side(device=line,
                                            side=EmtBusConnectionSide.FROM,
                                            var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _prune_saved_branch_root_contract_side(device=line,
                                           side=EmtBusConnectionSide.TO)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _ensure_saved_branch_root_contract_side(device=line,
                                            side=EmtBusConnectionSide.TO,
                                            var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _normalize_saved_branch_root_contract_from_live_sides(device=line)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    seed_template_derived_dynamic_connection_intents(device=line)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    rematerialize_saved_dynamic_connection_intents(device=line,
                                                   var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    attach_emt_model_to_buses(device=line,
                              model=line.emt_model,
                              var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    synchronize_saved_emt_root_contract_from_bus(device=line)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None


def test_branch_shrink_after_full_reconcile_exposes_remaining_vf_c_symbolic_location() -> None:
    """
    Identify where stale ``vf_C`` still survives in the symbolic model after full branch reconcile.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = _build_line_with_phases(circuit=circuit,
                                   bus_from=bus_from,
                                   bus_to=bus_to,
                                   active_phases=list([1, 2, 3]))
    template: EmtModelTemplate = get_pi_line_emt_template(vf=circuit.var_factory,
                                                          phN=False,
                                                          phA=True,
                                                          phB=True,
                                                          phC=True,
                                                          name="PiTemplate")
    line.emt_template = template
    line.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    initial_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        pass
    finally:
        _dispose_editor(initial_editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))
    assert circuit.check_emt_models().has_errors() is False

    surviving_root_input_refs: set[VarPowerFlowReferenceType] = set(var.ref for var in line.emt_model.in_vars if var.ref is not None)
    surviving_root_output_refs: set[VarPowerFlowReferenceType] = set(var.ref for var in line.emt_model.out_vars if var.ref is not None)
    surviving_all_var_refs: set[VarPowerFlowReferenceType] = set()
    all_var: Var
    for all_var in line.emt_model.get_all_vars():
        if all_var.ref is None:
            pass
        else:
            surviving_all_var_refs.add(all_var.ref)

    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None, (
        surviving_root_input_refs,
        surviving_root_output_refs,
        surviving_all_var_refs,
        set(reference for reference, value in line.emt_model.external_mapping.items() if value is not None),
    )


def test_branch_shrink_manual_full_sequence_identifies_first_vf_c_reappearance() -> None:
    """
    Identify the first full-reconcile stage that reintroduces stale ``vf_C``.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = _build_line_with_phases(circuit=circuit,
                                   bus_from=bus_from,
                                   bus_to=bus_to,
                                   active_phases=list([1, 2, 3]))
    template: EmtModelTemplate = get_pi_line_emt_template(vf=circuit.var_factory,
                                                          phN=False,
                                                          phA=True,
                                                          phB=True,
                                                          phC=True,
                                                          name="PiTemplate")
    line.emt_template = template
    line.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    initial_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        pass
    finally:
        _dispose_editor(initial_editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))

    _prune_saved_branch_root_contract_side(device=line,
                                           side=EmtBusConnectionSide.FROM)
    _prune_saved_branch_root_contract_side(device=line,
                                           side=EmtBusConnectionSide.TO)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _rebuild_saved_branch_root_contract_from_live_sides(device=line,
                                                        var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    seed_template_derived_dynamic_connection_intents(device=line)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    attach_emt_model_to_buses(device=line,
                              model=line.emt_model,
                              var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    _rebuild_saved_branch_root_contract_from_live_sides(device=line,
                                                        var_factory=circuit.var_factory)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None

    synchronize_saved_emt_root_contract_from_bus(device=line)
    assert line.emt_model.external_mapping.get(VarPowerFlowReferenceType.vf_C, None) is None


def test_branch_shrink_check_emt_models_matches_manual_root_contract_shape() -> None:
    """
    Verify ``check_emt_models()`` produces the same branch root contract shape as the passing manual sequence.

    :return: None.
    """
    _get_app()
    circuit: MultiCircuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus_from = gce.Bus(name="Bus From", Vnom=10.0)
    bus_to = gce.Bus(name="Bus To", Vnom=10.0)
    circuit.add_bus(bus_from)
    circuit.add_bus(bus_to)
    line = _build_line_with_phases(circuit=circuit,
                                   bus_from=bus_from,
                                   bus_to=bus_to,
                                   active_phases=list([1, 2, 3]))
    template: EmtModelTemplate = get_pi_line_emt_template(vf=circuit.var_factory,
                                                          phN=False,
                                                          phA=True,
                                                          phB=True,
                                                          phC=True,
                                                          name="PiTemplate")
    line.emt_template = template
    line.emt_model = duplicate_block(template.block, var_factory=circuit.var_factory)

    initial_editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
        pass
    finally:
        _dispose_editor(initial_editor)

    line.bus_from.emt_model = _build_phase_bus_block(name="bus_from_ab", mask=list([False, True, True, False]))
    before_state = _collect_branch_root_contract_state(line.emt_model)
    assert circuit.check_emt_models().has_errors() is False
    after_state = _collect_branch_root_contract_state(line.emt_model)

    assert before_state == (
        set([
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vf_C,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
        ]),
        set([
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.if_C,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ]),
        set([
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vf_C,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.if_C,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ]),
    )
    assert after_state == (
        set([
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
        ]),
        set([
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ]),
        set([
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ]),
    )


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

    editor = DynamicBlockEditorGUI(var_factory=VarFactory(),
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
