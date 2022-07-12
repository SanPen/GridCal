# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import numpy as np
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from GridCal.Engine.Devices.load import Load
from GridCal.Gui.GridEditorWidget.generic_graphics import *
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.GridEditorWidget.messages import *


class LoadGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        super(LoadGraphicItem, self).__init__(parent)

        self.w = 20.0
        self.h = 20.0

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.width = 4

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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        # triangle
        self.glyph = Polygon(self)
        self.glyph.setPolygon(QPolygonF([QPointF(0, 0), QPointF(self.w, 0), QPointF(self.w / 2, self.h)]))
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.addToGroup(self.glyph)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

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
        menu = QMenu()
        menu.addSection("Load")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

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

        menu.exec_(event.screenPos())

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this load', 'Remove load')
        else:
            ok = True

        if ok:
            self.diagramScene.removeItem(self.nexus)
            self.diagramScene.removeItem(self)
            self.api_object.bus.loads.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
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

    def plot(self):
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

