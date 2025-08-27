# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING, Union
from PySide6.QtWidgets import QMenu
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from VeraGrid.Gui.messages import yes_no_question
from VeraGrid.Gui.Diagrams.Editors.transformer_editor import TransformerEditor
from VeraGrid.Gui.Diagrams.Editors.transformer_taps_editor import TransformerTapsEditor
from VeraGridEngine.Devices.Branches.transformer import Transformer2W, TransformerType
from VeraGridEngine.enumerations import DeviceType, TapModuleControl

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class TransformerGraphicItem(LineGraphicTemplateItem):
    """
    TransformerGraphicItem
    """

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem],
                 editor: SchematicWidget,
                 width=5,
                 api_object: Transformer2W = None,
                 draw_labels: bool = True):
        """

        :param from_port:
        :param to_port:
        :param editor:
        :param width:
        :param api_object:
        """
        LineGraphicTemplateItem.__init__(self=self,
                                         from_port=from_port,
                                         to_port=to_port,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object,
                                         draw_labels=draw_labels)

    @property
    def api_object(self) -> Transformer2W:
        return self._api_object

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Transformer")

            add_menu_entry(menu=menu,
                           text="Active",
                           function_ptr=self.enable_disable_toggle,
                           checkeable=True,
                           checked_value=self.api_object.active)

            add_menu_entry(menu=menu,
                           text="Draw labels",
                           function_ptr=self.enable_disable_label_drawing,
                           checkeable=True,
                           checked_value=self.draw_labels)

            add_menu_entry(menu=menu,
                           text="Delete",
                           function_ptr=self.delete,
                           icon_path=":/Icons/icons/delete3.svg")

            add_menu_entry(menu=menu,
                           text="Edit template",
                           function_ptr=self.edit,
                           icon_path=":/Icons/icons/edit.svg")

            menu.addSection('Tap changer')

            add_menu_entry(menu=menu,
                           text="Edit tap changer",
                           function_ptr=self.edit_tap_changer,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Tap up",
                           function_ptr=self.tap_up,
                           icon_path=":/Icons/icons/up.svg")

            add_menu_entry(menu=menu,
                           text="Tap down",
                           function_ptr=self.tap_down,
                           icon_path=":/Icons/icons/down.svg")

            add_menu_entry(menu=menu,
                           text="Control V from",
                           function_ptr=self.control_v_from,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Control V to",
                           function_ptr=self.control_v_to,
                           icon_path=":/Icons/icons/edit.svg")

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Plot profiles",
                           function_ptr=self.plot_profiles,
                           icon_path=":/Icons/icons/plot.svg")

            add_menu_entry(menu=menu,
                           text="Add to catalogue",
                           function_ptr=self.add_to_catalogue,
                           icon_path=":/Icons/icons/Catalogue.svg")

            add_menu_entry(menu=menu,
                           text="Assign rate to profile",
                           function_ptr=self.assign_rate_to_profile,
                           icon_path=":/Icons/icons/assign_to_profile.svg")

            add_menu_entry(menu=menu,
                           text="Assign active state to profile",
                           function_ptr=self.assign_status_to_profile,
                           icon_path=":/Icons/icons/assign_to_profile.svg")

            add_menu_entry(menu=menu,
                           text="Flip",
                           function_ptr=self.flip_connections,
                           icon_path=":/Icons/icons/redo.svg")

            add_menu_entry(menu=menu,
                           text="Change bus",
                           function_ptr=self.change_bus,
                           icon_path=":/Icons/icons/move_bus.svg")

            menu.exec_(event.screenPos())

        else:
            pass

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """

        if self.api_object is not None:
            if self.api_object.device_type in [DeviceType.Transformer2WDevice, DeviceType.LineDevice]:
                # trigger the editor
                self.edit()
            elif self.api_object.device_type is DeviceType.SwitchDevice:
                # change state
                self.enable_disable_toggle()

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        templates = self.editor.circuit.transformer_types
        current_template = self.api_object.template
        dlg = TransformerEditor(self.api_object, Sbase,
                                modify_on_accept=True,
                                templates=templates,
                                current_template=current_template)
        if dlg.exec():
            pass

    def edit_tap_changer(self):
        """

        :return:
        """

        dlg = TransformerTapsEditor(api_object=self.api_object.tap_changer)
        if dlg.exec():
            pass

    def show_transformer_editor(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase

        if self.api_object.template is not None:
            # automatically pick the template
            if isinstance(self.api_object.template, TransformerType):
                self.editor.circuit.add_transformer_type(self.api_object.template)
            else:
                # raise dialogue to set the template
                dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
                if dlg.exec():
                    tpe = dlg.get_template()
                    self.editor.circuit.add_transformer_type(tpe)
        else:
            # raise dialogue to set the template
            dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
            if dlg.exec():
                tpe = dlg.get_template()
                self.editor.circuit.add_transformer_type(tpe)

    def add_to_catalogue(self):
        """
        Add this object to the catalogue
        :return:
        """

        ok = yes_no_question(text="A template will be generated using this transformer values",
                             title="Add transformer type")

        if ok:
            tpe = self.api_object.get_transformer_type(Sbase=self.editor.circuit.Sbase)

            self.editor.circuit.add_transformer_type(tpe)

    def flip_connections(self):
        """
        Flip connections
        :return:
        """
        self.api_object.flip()

    def tap_up(self):
        """
        Set one tap up
        """
        self.api_object.tap_up()

    def tap_down(self):
        """
        Set one tap down
        """
        self.api_object.tap_down()

    def control_v_from(self):
        """

        :return:
        """
        self.api_object.regulation_bus = self.api_object.bus_from
        self.api_object.tap_module_control_mode = TapModuleControl.Vm

    def control_v_to(self):
        """

        :return:
        """
        self.api_object.regulation_bus = self.api_object.bus_to
        self.api_object.tap_module_control_mode = TapModuleControl.Vm
