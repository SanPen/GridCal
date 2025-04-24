# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6 import QtWidgets

from GridCal.Gui.Diagrams.generic_graphics import Square
from GridCalEngine.Devices.Injections.controllable_shunt import ControllableShunt
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.Diagrams.Editors.controllable_shunt_editor import ControllableShuntEditor
from GridCal.Gui.gui_functions import add_menu_entry

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class ControllableShuntGraphicItem(InjectionTemplateGraphicItem):
    """
    ExternalGrid graphic item
    """

    def __init__(self, parent, api_obj: ControllableShunt, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='external grid',
                                              w=40,
                                              h=40)
        self.set_glyph(glyph=Square(self, 40, 40, "C", self.update_nexus))

    @property
    def api_object(self) -> ControllableShunt:
        return self._api_object

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QtWidgets.QMenu()
        menu.addSection("Controllable shunt")

        add_menu_entry(menu=menu,
                       text="Active",
                       checkeable=True,
                       checked_value=self.api_object.active,
                       function_ptr=self.enable_disable_toggle)

        add_menu_entry(menu=menu,
                       text="Editor",
                       function_ptr=self.edit,
                       icon_path=":/Icons/icons/edit.svg")

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       function_ptr=self.plot,
                       icon_path=":/Icons/icons/plot.svg")

        add_menu_entry(menu=menu,
                       text="Delete",
                       function_ptr=self.delete,
                       icon_path=":/Icons/icons/delete3.svg")

        add_menu_entry(menu=menu,
                       text="Change bus",
                       function_ptr=self.change_bus,
                       icon_path=":/Icons/icons/move_bus.svg")

        menu.exec_(event.screenPos())

    def edit(self):
        """
        Call the edit dialogue
        :return:
        """
        dlg = ControllableShuntEditor(api_object=self.api_object)
        if dlg.exec():
            self.api_object.active_steps = dlg.get_active_steps()
            self.api_object.g_steps = dlg.get_g_steps()
            self.api_object.Gmax = self.api_object.g_steps.max()
            self.api_object.Gmin = self.api_object.g_steps.min()
            self.api_object.b_steps = dlg.get_b_steps()
            self.api_object.Bmax = self.api_object.b_steps.max()
            self.api_object.Bmin = self.api_object.b_steps.min()
