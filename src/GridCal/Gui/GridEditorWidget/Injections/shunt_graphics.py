# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from PySide6 import QtWidgets
from PySide6.QtCore import QPointF, QLineF
from PySide6.QtGui import QPen, QIcon, QPixmap
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Line
from GridCal.Gui.GridEditorWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.messages import yes_no_question


class ShuntGraphicItem(InjectionTemplateGraphicItem):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              diagramScene=diagramScene,
                                              device_type_name='generator',
                                              w=15,
                                              h=30)

        pen = QPen(self.color, self.width, self.style)

        lines_data = list()
        lines_data.append(QLineF(QPointF(self.w / 2, 0), QPointF(self.w / 2, self.h * 0.4)))
        lines_data.append(QLineF(QPointF(0, self.h * 0.4), QPointF(self.w, self.h * 0.4)))
        lines_data.append(QLineF(QPointF(0, self.h * 0.6), QPointF(self.w, self.h * 0.6)))
        lines_data.append(QLineF(QPointF(self.w / 2, self.h * 0.6), QPointF(self.w / 2, self.h)))
        lines_data.append(QLineF(QPointF(0, self.h * 1), QPointF(self.w, self.h * 1)))
        lines_data.append(QLineF(QPointF(self.w * 0.15, self.h * 1.1), QPointF(self.w * 0.85, self.h * 1.1)))
        lines_data.append(QLineF(QPointF(self.w * 0.3, self.h * 1.2), QPointF(self.w * 0.7, self.h * 1.2)))

        self.lines = list()
        for l in lines_data:
            l1 = Line(self)
            l1.setLine(l)
            l1.setPen(pen)
            self.lines.append(l1)
            self.addToGroup(l1)

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

        pen = QPen(self.color, self.width, self.style)
        self.nexus.setPen(pen)
        for l in self.lines:
            l.setPen(pen)

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
        menu.addSection("Shunt")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

        pc = menu.addAction('Voltage control')
        pc.setCheckable(True)
        pc.setChecked(self.api_object.is_controlled)
        pc.triggered.connect(self.enable_disable_control_toggle)

        pa = menu.addAction('Plot profiles')
        plot_icon = QIcon()
        plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
        pa.setIcon(plot_icon)
        pa.triggered.connect(self.plot)

        da = menu.addAction('Delete')
        del_icon = QIcon()
        del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        rabf = menu.addAction('Change bus')
        move_bus_icon = QIcon()
        move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
        rabf.setIcon(move_bus_icon)
        rabf.triggered.connect(self.change_bus)

        menu.exec_(event.screenPos())

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this shunt', 'Remove shunt')
        else:
            ok = True

        if ok:
            self.diagramScene.removeItem(self.nexus)
            self.diagramScene.removeItem(self)
            self.api_object.bus.shunts.remove(self.api_object)

    def enable_disable_toggle(self):
        """
        Enable / Disable device
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.diagramScene.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.diagramScene.set_active_status_to_profile(self.api_object, override_question=True)

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

        pen = QPen(self.color, self.width, self.style)

        for l in self.childItems():
            l.setPen(pen)

    def plot(self):
        """
        Plot API objects profiles
        """
        # time series object from the last simulation
        ts = self.diagramScene.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.editable_headers,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

