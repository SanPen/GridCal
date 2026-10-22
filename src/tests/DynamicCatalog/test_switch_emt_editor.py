from __future__ import annotations

import sys

from PySide6 import QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DynamicSimulationMode, DeviceType

class _ApiStub:
    __slots__ = ("name", "rms_template", "emt_template", "device_type")

    def __init__(self) -> None:
        self.name = "Stub"
        self.rms_template = None
        self.emt_template = None
        self.device_type = DeviceType.NoDevice


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    return app


def _build_editor() -> DynamicBlockEditorGUI:
    _get_app()
    editor = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=_ApiStub(),
        current_theme="Light",
        circuit=MultiCircuit(),
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
    )
    editor.show()
    editor.activateWindow()
    return editor
#
#
# def test_switch_emt_block_item_is_created_from_modal(override_attrs) -> None:
#     editor = _build_editor()
#
#     class _SwitchDialogStub:
#         def __init__(self, parent=None) -> None:
#             _unused = parent
#
#         def exec(self) -> int:
#             return int(QtWidgets.QDialog.DialogCode.Accepted)
#
#         def get_switch_configuration(self) -> dict[str, object]:
#             return dict({
#                 "phA": True,
#                 "phB": True,
#                 "phC": True,
#                 "signal_controlled": True,
#                 "seed_from_pf_active": True,
#                 "initial_closed": True,
#                 "use_device_conductance": True,
#                 "manual_closed_conductance": 1.0e4,
#                 "open_conductance": 1.0e-8,
#                 "switch_time_constant": 1.0e-4,
#                 "command_threshold": 0.5,
#             })
#
#     override_attrs.setattr(dynamic_block_editor_module, "SwitchEmtDialog", _SwitchDialogStub)
#     block_item = editor.create_library_payload_item(BlockType.SWITCH_EMT, 10.0, 20.0)
#
#     assert block_item is not None
#     assert any(var.name.startswith("switch_closed_mode_") for var in block_item.subsys.mode_dict.keys())
#     assert any(var.name.startswith("switch_cmd_") for var in block_item.subsys.in_vars)
#
#     editor.has_unapplied_changes = False
#     editor.close()


class _NavigationDelegateStub:
    """Captures navigation requests for testing."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[Block] = list()

    def navigate_to_block(self, block: Block) -> None:
        self.calls.append(block)


def test_scene_edit_dispatch_navigates_via_delegate(override_attrs) -> None:
    editor = _build_editor()
    block = Block(name="dispatch_edit_block")
    template: EmtModelTemplate = EmtModelTemplate(name="dispatch_edit_block")
    template.block = block
    block_item = editor.create_materialized_template_block_item(template, editor.var_factory, 10.0, 20.0)

    assert block_item is not None

    delegate = _NavigationDelegateStub()
    editor.set_navigation_delegate(delegate)

    editor.edit_scene_item(block_item)

    assert len(delegate.calls) == 1
    assert delegate.calls[0] is block_item.subsys

    editor.has_unapplied_changes = False
    editor.close()


def test_edit_scene_item_ignores_navigation_without_delegate() -> None:
    editor = _build_editor()
    block = Block(name="no_delegate_block")
    template: EmtModelTemplate = EmtModelTemplate(name="no_delegate_block")
    template.block = block
    block_item = editor.create_materialized_template_block_item(template, editor.var_factory, 10.0, 20.0)

    assert block_item is not None
    assert editor._navigation_delegate is None

    # Should not raise when no delegate is set
    editor.edit_scene_item(block_item)

    editor.has_unapplied_changes = False
    editor.close()
