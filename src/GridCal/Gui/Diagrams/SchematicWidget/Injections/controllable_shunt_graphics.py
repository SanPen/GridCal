# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6 import QtWidgets, QtGui
from GridCalEngine.Devices.Injections.controllable_shunt import ControllableShunt, DeviceType
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Square
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Injections.controllable_shunt_editor import ControllableShuntEditor
from GridCal.Gui.messages import yes_no_question
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

        pen = QtGui.QPen(self.color, self.width, self.style)

        self.glyph = Square(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QtWidgets.QGraphicsTextItem('CS', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_nexus(self.pos())

    def recolour_mode(self):
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

        pen = QtGui.QPen(self.color, self.width, self.style)
        self.glyph.setPen(pen)
        self.nexus.setPen(pen)
        self.label.setDefaultTextColor(self.color)

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
                       function_ptr=self.remove,
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
        self.glyph.setPen(QtGui.QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)

    def plot(self):
        """
        Plot API objects profiles
        """
        # time series object from the last simulation
        ts = self.editor.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        self.editor.set_editor_model(api_object=self.api_object)
