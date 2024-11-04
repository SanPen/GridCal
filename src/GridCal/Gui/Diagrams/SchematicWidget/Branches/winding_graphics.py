

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING, Union
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.Devices.Branches.winding import Winding
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class WindingGraphicItem(LineGraphicTemplateItem):

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem, None],
                 editor: SchematicWidget,
                 width=5,
                 api_object: Winding = None,
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

        self.parent_tr3_graphics_item = None
        self.winding_number = 0

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Winding")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            add_menu_entry(menu=menu,
                           text="Draw labels",
                           function_ptr=self.enable_disable_label_drawing,
                           checkeable=True,
                           checked_value=self.draw_labels)

            # menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra4 = menu.addAction('Assign rate to profile')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.assign_rate_to_profile)

            ra5 = menu.addAction('Assign active state to profile')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.assign_status_to_profile)

            # menu.addSeparator()

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            menu.exec_(event.screenPos())
        else:
            pass

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            dtype = self.api_object.device_type.value
            ok = yes_no_question(f'Do you want to remove the {dtype} {self.api_object.name}?',
                                 'Remove branch')
        else:
            ok = True

        if ok:
            self.editor.circuit.delete_branch(self.api_object)
            self.editor.delete_diagram_element(self.api_object)

            # unregister the winding
            self.parent_tr3_graphics_item.remove_winding(self.winding_number)
