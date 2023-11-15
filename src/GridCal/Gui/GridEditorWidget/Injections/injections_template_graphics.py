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
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItemGroup
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg
from GridCalEngine.Core.Devices.Injections.injection_template import InjectionTemplate


class InjectionTemplateGraphicItem(QGraphicsItemGroup):
    """
    InjectionTemplateGraphicItem
    """

    def __init__(self, parent, api_obj: InjectionTemplate, diagramScene, device_type_name, w, h):
        """

        :param parent:
        :param api_obj:
        """
        super(InjectionTemplateGraphicItem, self).__init__(parent)

        self.w = w
        self.h = h

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        self.device_type_name = device_type_name

        # Properties of the container:
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
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
        self.diagramScene.addItem(self.nexus)

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
        return pen

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

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this ' + self.device_type_name + '?',
                                 'Remove load')
        else:
            ok = True

        if ok:
            self.diagramScene.removeItem(self.nexus)
            self.diagramScene.removeItem(self)
            self.api_object.bus.loads.remove(self.api_object)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.editable_headers,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def change_bus(self):
        """
        Change the generator bus
        """
        editor = self.diagramScene.parent()
        idx_bus_list = editor.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == self.api_object.bus:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
            elif idx_bus_list[1][1] == self.api_object.bus:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
            else:
                error_msg("The bus to change has not been selected!", 'Change bus')
                return

            ok = yes_no_question(
                text="Are you sure that you want to relocate the bus from {0} to {1}?".format(old_bus.name,
                                                                                              new_bus.name),
                title='Change bus')

            if ok:
                self.api_object.bus = new_bus
                new_bus_graphic_item.add_object(api_obj=self.api_object)
                new_bus_graphic_item.update()
                self.remove(ask=False)
        else:
            warning_msg("you have to select the origin and destination buses!",
                        title='Change bus')
