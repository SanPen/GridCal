# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (QMenu, QGraphicsTextItem)
from GridCalEngine.Devices.Fluid.fluid_turbine import FluidTurbine
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Circle
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class FluidTurbineGraphicItem(InjectionTemplateGraphicItem):
    """
    FluidTurbineGraphicItem
    """

    def __init__(self, parent, api_obj: FluidTurbine, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='fluid_turbine',
                                              w=40,
                                              h=40)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Circle(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('T', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_nexus(self.pos())

    def mouseDoubleClickEvent(self, event):
        """

        :param event:
        """
        pass

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
            else:
                self.color = DEACTIVATED['color']
                self.style = DEACTIVATED['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        pen = QPen(self.color, self.width, self.style)
        self.glyph.setPen(pen)
        self.nexus.setPen(pen)
        self.label.setDefaultTextColor(self.color)

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Turbine")

        add_menu_entry(menu=menu,
                       text="Plot fluid profiles",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot)

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       icon_path=":/Icons/icons/delete3.svg",
                       function_ptr=self.remove)

        add_menu_entry(menu=menu,
                       text="Change bus",
                       icon_path=":/Icons/icons/move_bus.svg",
                       function_ptr=self.change_bus)

        menu.exec_(event.screenPos())

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.editor.set_active_status_to_profile(self.api_object, override_question=True)

    def enable_disable_control_toggle(self):
        """
        Enable / Disable device voltage control
        """
        if self.api_object is not None:
            self.api_object.is_controlled = not self.api_object.is_controlled

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)

    def plot(self):
        """
        Plot API objects profiles
        """
        # time series object from the last simulation
        ts = self.editor.circuit.time_profile

        # plot the profiles
        # self.api_object.plot_profiles(time=ts)
