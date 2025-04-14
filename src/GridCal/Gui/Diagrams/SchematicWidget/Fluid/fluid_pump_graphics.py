# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (QMenu)
from GridCalEngine.Devices.Fluid.fluid_pump import FluidPump
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, Circle
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class FluidPumpGraphicItem(InjectionTemplateGraphicItem):
    """
    FluidPumpGraphicItem
    """

    def __init__(self, parent, api_obj: FluidPump, editor: "SchematicWidget"):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='fluid_pump',
                                              w=40,
                                              h=40,
                                              glyph=Circle(self, 40, 40, "P")
                                              )

    @property
    def api_object(self) -> FluidPump:
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        return self._editor

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

        pen = QPen(self.color, self.width, self.style)
        self.glyph.setPen(pen)
        self.nexus.setPen(pen)

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Pump")

        add_menu_entry(menu=menu,
                       text="Plot fluid profiles",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot)

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       icon_path=":/Icons/icons/delete3.svg",
                       function_ptr=self.delete)

        add_menu_entry(menu=menu,
                       text="Change bus",
                       icon_path=":/Icons/icons/move_bus.svg",
                       function_ptr=self.change_bus)

        menu.exec_(event.screenPos())
