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
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItemGroup
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import INJECTION_DEVICE_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class InjectionTemplateGraphicItem(GenericDiagramWidget, QGraphicsItemGroup):
    """
    InjectionTemplateGraphicItem
    """

    def __init__(self,
                 parent,
                 api_obj: INJECTION_DEVICE_TYPES,
                 device_type_name: str,
                 w: int,
                 h: int,
                 editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param device_type_name:
        :param w:
        :param h:
        """
        GenericDiagramWidget.__init__(self, parent=parent, api_object=api_obj, editor=editor, draw_labels=True)
        QGraphicsItemGroup.__init__(self, parent)

        self.w = w
        self.h = h

        self.scale = 1.0

        self.device_type_name = device_type_name

        # Properties of the container:
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.width = 4

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        self.editor.add_to_scene(self.nexus)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_nexus(self.pos())

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        pen = QPen(self.color, self.width, self.style)
        self.nexus.setPen(pen)
        return pen

    def update_nexus(self, pos):
        """
        Update the nexus line that joins the parent and this object
        :param pos: position of this object
        """
        parent_pt = self.parentItem().get_nexus_point()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y(),
            parent_pt.x(),
            parent_pt.y(),
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question(f'Are you sure that you want to remove this {self.device_type_name}?',
                                 f'Remove {self.api_object.name}')
        else:
            ok = True

        if ok:
            self.editor.remove_from_scene(self.nexus)
            self.editor.remove_element(device=self.api_object, graphic_object=self)
            self.editor.remove_from_scene(self)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        self.editor.set_editor_model(api_object=self.api_object,
                                     dictionary_of_lists={
                                         DeviceType.GeneratorDevice: self.editor.circuit.get_generators(),
                                         DeviceType.BusDevice: self.editor.circuit.get_buses(),
                                         DeviceType.ConnectivityNodeDevice: self.editor.circuit.get_connectivity_nodes(),
                                     })

    def change_bus(self):
        """
        Change the generator bus
        """
        idx_bus_list = self.editor.get_selected_buses()

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
                text=f"Are you sure that you want to relocate the bus from {old_bus.name} to {new_bus.name}?",
                title='Change bus')

            if ok:
                self.api_object.bus = new_bus
                new_bus_graphic_item.add_object(api_obj=self.api_object)
                new_bus_graphic_item.update()
                self.remove(ask=False)
        else:
            warning_msg("you have to select the origin and destination buses!",
                        title='Change bus')

    def rescale(self, scale: float = 1.0):
        """

        :param scale:
        :return:
        """
        self.scale = scale
