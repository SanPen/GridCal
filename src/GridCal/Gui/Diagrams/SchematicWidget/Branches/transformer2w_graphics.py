# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from __future__ import annotations
from typing import TYPE_CHECKING, Union
from PySide6.QtWidgets import QMenu
from GridCal.Gui.GuiFunctions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer_editor import TransformerEditor
from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer_taps_editor import TransformerTapsEditor
from GridCalEngine.Devices.Branches.transformer import Transformer2W, TransformerType
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


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
                           function_ptr=self.remove,
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
        if dlg.exec_():
            pass

    def edit_tap_changer(self):
        """

        :return:
        """

        dlg = TransformerTapsEditor(api_object=self.api_object.tap_changer)
        if dlg.exec_():
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
                if dlg.exec_():
                    tpe = dlg.get_template()
                    self.editor.circuit.add_transformer_type(tpe)
        else:
            # raise dialogue to set the template
            dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
            if dlg.exec_():
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
