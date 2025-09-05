# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING, Union
from PySide6.QtWidgets import QMenu
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGrid.Gui.messages import yes_no_question

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class HvdcGraphicItem(LineGraphicTemplateItem):

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem],
                 editor: SchematicWidget,
                 width=5,
                 api_object: HvdcLine = None,
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
    def api_object(self) -> HvdcLine:
        return self._api_object

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("HVDC line")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            add_menu_entry(menu=menu,
                           text="Draw labels",
                           icon_path="",
                           function_ptr=self.enable_disable_label_drawing,
                           checkeable=True,
                           checked_value=self.draw_labels)

            # pe2 = menu.addAction('Convert to Multi-terminal')
            # pe2.triggered.connect(self.convert_to_multi_terminal)

            add_menu_entry(menu=menu,
                           text="Change bus",
                           icon_path=":/Icons/icons/move_bus.svg",
                           function_ptr=self.change_bus)

            add_menu_entry(menu=menu,
                           text="Convert to VSC multi-terminal",
                           icon_path=":/Icons/icons/vsc.svg",
                           function_ptr=self.convert_to_multi_terminal)

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Plot profiles",
                           icon_path=":/Icons/icons/plot.svg",
                           function_ptr=self.plot_profiles)

            add_menu_entry(menu=menu,
                           text="Assign rate to profile",
                           icon_path=":/Icons/icons/assign_to_profile.svg",
                           function_ptr=self.assign_rate_to_profile)

            add_menu_entry(menu=menu,
                           text="Assign active state to profile",
                           icon_path=":/Icons/icons/assign_to_profile.svg",
                           function_ptr=self.assign_status_to_profile)

            add_menu_entry(menu=menu,
                           text="Delete",
                           icon_path=":/Icons/icons/delete3.svg",
                           function_ptr=self.delete)

            menu.exec_(event.screenPos())
        else:
            pass

    def convert_to_multi_terminal(self):
        """
        Convert this HvdcLine to a vsc + DC line system
        """
        ok = yes_no_question('Do you want to change the HvdcLine by 2 VSC converters + 1 DC Line?',
                             'Change by a VSC system')

        if ok:
            self.editor.convert_hvdc_line_to_vsc_system(hvdc_line=self.api_object)

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_hvdc().index(self.api_object)
        self.editor.plot_hvdc_branch(i, self.api_object)
