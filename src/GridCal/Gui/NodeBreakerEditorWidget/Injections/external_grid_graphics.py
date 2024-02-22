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
from typing import TYPE_CHECKING
from PySide6 import QtWidgets, QtGui, QtCore
from GridCalEngine.Core.Devices.Injections.battery import Battery, DeviceType
from GridCal.Gui.NodeBreakerEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Square
from GridCal.Gui.NodeBreakerEditorWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.messages import yes_no_question

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.NodeBreakerEditorWidget.node_breaker_editor_widget import NodeBreakerEditorWidget


class ExternalGridGraphicItem(InjectionTemplateGraphicItem):
    """
    ExternalGrid graphic item
    """
    def __init__(self, parent, api_obj: Battery, editor: NodeBreakerEditorWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='generator',
                                              w=40,
                                              h=40)

        pen = QtGui.QPen(self.color, self.width, self.style)

        self.glyph = Square(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QtWidgets.QGraphicsTextItem('E', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

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

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QtWidgets.QMenu()
        menu.addSection("External grid")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profiles')
        plot_icon = QtGui.QIcon()
        plot_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/plot.svg"))
        pa.setIcon(plot_icon)
        pa.triggered.connect(self.plot)

        da = menu.addAction('Delete')
        del_icon = QtGui.QIcon()
        del_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        rabf = menu.addAction('Change bus')
        move_bus_icon = QtGui.QIcon()
        move_bus_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/move_bus.svg"))
        rabf.setIcon(move_bus_icon)
        rabf.triggered.connect(self.change_bus)

        menu.exec_(event.screenPos())

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this external grid', 'Remove external grid')
        else:
            ok = True

        if ok:
            self.editor.remove_from_scene(self.nexus)
            self.editor.remove_from_scene(self)
            self.api_object.bus.batteries.remove(self.api_object)

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
        self.editor.set_editor_model(api_object=self.api_object,
                                     dictionary_of_lists={DeviceType.Technology.value: self.editor.circuit.technologies, })

