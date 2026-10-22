from __future__ import annotations

import sys
from types import SimpleNamespace

from PySide6 import QtCore, QtWidgets

import VeraGridEngine.api as vge
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_handler import DynamicEventParameterCandidate
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_handler import DynamicEventsHandler
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_page import DynamicEventsPage
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import collect_block_runtime_event_parameters
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicSimulationMode, VarPowerFlowReferenceType


def get_qt_application() -> QtWidgets.QApplication:
    """Return the process QApplication required by widget tests.

    :return: Existing or newly created QApplication.
    """
    application: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if application is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return application


def build_dynamic_targets() -> tuple[vge.MultiCircuit, vge.Load, vge.Load, Var, Var, vge.RmsEventsGroup]:
    """Build two RMS devices with one event parameter each.

    :return: Circuit, devices, parameters and shared event group.
    """
    circuit: vge.MultiCircuit = vge.MultiCircuit()
    bus: vge.Bus = vge.Bus(name="Event bus", Vnom=10.0)
    circuit.add_bus(bus)
    first_load: vge.Load = vge.Load(name="First event load")
    second_load: vge.Load = vge.Load(name="Second event load")
    circuit.add_load(bus=bus, api_obj=first_load)
    circuit.add_load(bus=bus, api_obj=second_load)
    first_parameter: Var = circuit.var_factory.add_var("first_event_parameter")
    second_parameter: Var = circuit.var_factory.add_var("second_event_parameter")
    first_event_values: dict[Var, Const] = dict()
    second_event_values: dict[Var, Const] = dict()
    first_event_values[first_parameter] = Const(0.0)
    second_event_values[second_parameter] = Const(0.0)
    first_load.rms_model = Block(event_dict=first_event_values)
    second_load.rms_model = Block(event_dict=second_event_values)
    group: vge.RmsEventsGroup = vge.RmsEventsGroup(name="RMS group")
    circuit.add_rms_events_group(obj=group)
    return circuit, first_load, second_load, first_parameter, second_parameter, group


def test_global_parameter_catalog_contains_every_device_parameter() -> None:
    """The global RMS catalog must include parameters from every RMS device.

    :return: None.
    """
    _application: QtWidgets.QApplication = get_qt_application()
    circuit: vge.MultiCircuit
    first_load: vge.Load
    second_load: vge.Load
    first_parameter: Var
    second_parameter: Var
    _group: vge.RmsEventsGroup
    circuit, first_load, second_load, first_parameter, second_parameter, _group = build_dynamic_targets()
    handler: DynamicEventsHandler = DynamicEventsHandler(
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
    )

    assert len(handler.candidates) == 2
    assert handler.candidate_for_device_parameter(first_load, first_parameter) is not None
    assert handler.candidate_for_device_parameter(second_load, second_parameter) is not None


def test_group_checkbox_updates_real_group_immediately() -> None:
    """The right-tree group checkbox must write directly to the circuit asset.

    :return: None.
    """
    _application: QtWidgets.QApplication = get_qt_application()
    circuit: vge.MultiCircuit
    _first_load: vge.Load
    _second_load: vge.Load
    _first_parameter: Var
    _second_parameter: Var
    group: vge.RmsEventsGroup
    circuit, _first_load, _second_load, _first_parameter, _second_parameter, group = build_dynamic_targets()
    handler: DynamicEventsHandler = DynamicEventsHandler(circuit=circuit, mode=DynamicSimulationMode.RMS)
    group_index: QtCore.QModelIndex = handler.events_model.index_for_group(group=group)

    assert handler.events_model.setData(
        group_index,
        QtCore.Qt.CheckState.Unchecked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    assert not group.active


def test_parameter_drag_payload_adds_event_to_group() -> None:
    """A UUID-sized parameter UID must survive the complete drag payload.

    :return: None.
    """
    _application: QtWidgets.QApplication = get_qt_application()
    circuit: vge.MultiCircuit
    first_load: vge.Load
    _second_load: vge.Load
    first_parameter: Var
    _second_parameter: Var
    group: vge.RmsEventsGroup
    circuit, first_load, _second_load, first_parameter, _second_parameter, group = build_dynamic_targets()
    handler: DynamicEventsHandler = DynamicEventsHandler(circuit=circuit, mode=DynamicSimulationMode.RMS)

    type_index: QtCore.QModelIndex = handler.parameters_model.index(0, 0)
    device_index: QtCore.QModelIndex = handler.parameters_model.index(0, 0, type_index)
    parameter_index: QtCore.QModelIndex = handler.parameters_model.index(0, 0, device_index)
    mime_data: QtCore.QMimeData = handler.parameters_model.mimeData([parameter_index])
    group_index: QtCore.QModelIndex = handler.events_model.index_for_group(group=group)

    assert handler.events_model.dropMimeData(
        mime_data,
        QtCore.Qt.DropAction.CopyAction,
        -1,
        0,
        group_index,
    )
    assert len(circuit.rms_events) == 1
    assert circuit.rms_events[0].device is first_load
    assert circuit.rms_events[0].parameter is first_parameter


def test_global_events_page_adds_default_event_to_selected_group() -> None:
    """Toolbar addition must use the deterministic first device and parameter.

    :return: None.
    """
    _application: QtWidgets.QApplication = get_qt_application()
    circuit: vge.MultiCircuit
    first_load: vge.Load
    _second_load: vge.Load
    first_parameter: Var
    _second_parameter: Var
    group: vge.RmsEventsGroup
    circuit, first_load, _second_load, first_parameter, _second_parameter, group = build_dynamic_targets()
    page: DynamicEventsPage = DynamicEventsPage(circuit=circuit, mode=DynamicSimulationMode.RMS)
    page._select_group(group=group)
    page.add_event()

    assert len(circuit.rms_events) == 1
    assert circuit.rms_events[0].group is group
    assert circuit.rms_events[0].device is first_load
    assert circuit.rms_events[0].parameter is first_parameter
    page.prepare_to_delete()
    page.deleteLater()


def test_changing_event_device_resets_parameter_to_compatible_default() -> None:
    """A device edit must replace the event parameter with one from that device.

    :return: None.
    """
    _application: QtWidgets.QApplication = get_qt_application()
    circuit: vge.MultiCircuit
    first_load: vge.Load
    second_load: vge.Load
    first_parameter: Var
    second_parameter: Var
    group: vge.RmsEventsGroup
    circuit, first_load, second_load, first_parameter, second_parameter, group = build_dynamic_targets()
    handler: DynamicEventsHandler = DynamicEventsHandler(circuit=circuit, mode=DynamicSimulationMode.RMS)
    first_candidate: DynamicEventParameterCandidate | None = handler.candidate_for_device_parameter(
        device=first_load,
        parameter=first_parameter,
    )
    assert first_candidate is not None
    assert handler.add_candidate_to_group(group=group, candidate=first_candidate)
    event: vge.RmsEvent = circuit.rms_events[0]
    event_index: QtCore.QModelIndex = handler.events_model.index_for_event(event=event)

    assert handler.events_model.setData(
        event_index,
        second_load,
        QtCore.Qt.ItemDataRole.EditRole,
    )
    assert event.device is second_load
    assert event.parameter is second_parameter


def test_collect_block_runtime_event_parameters_includes_child_modes() -> None:
    """Parameter discovery must include discrete modes in child blocks.

    :return: None.
    """
    mode_parameter: Var = VarFactory().add_var("switch_closed_mode_child")
    mode_values: dict[Var, float] = dict()
    mode_values[mode_parameter] = 0.0
    child_block: Block = Block(mode_dict=mode_values)
    root_block: Block = Block(children=list((child_block,)))
    parameters: list[Var]
    mode_uids: set[int]
    parameters, mode_uids = collect_block_runtime_event_parameters(block=root_block)

    assert parameters == list((mode_parameter,))
    assert mode_uids == set((mode_parameter.uid,))


def test_switch_sequence_candidates_use_reference_instead_of_name() -> None:
    factory = VarFactory()
    renamed_mode = factory.add_var("contact_position", reference=VarPowerFlowReferenceType.switch_closed_mode)
    unrelated_mode = factory.add_var("switch_closed_mode_unrelated")
    switch = vge.Switch(name="SW")
    mapped = DynamicEventParameterCandidate(switch, renamed_mode, True)
    unrelated = DynamicEventParameterCandidate(switch, unrelated_mode, True)
    page = SimpleNamespace(handler=SimpleNamespace(candidates=[mapped, unrelated]))
    assert DynamicEventsPage._switch_candidates(page) == [mapped]
