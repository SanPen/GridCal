# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING, List
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItemGroup
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCalEngine.Devices.types import INJECTION_DEVICE_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.cn_graphics import CnGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.busbar_graphics import BusBarGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
    NODE_GRAPHIC = BusGraphicItem | CnGraphicItem | BusBarGraphicItem | FluidNodeGraphicItem


class InjectionTemplateGraphicItem(GenericDiagramWidget, QGraphicsItemGroup):
    """
    InjectionTemplateGraphicItem
    """

    def __init__(self,
                 parent: NODE_GRAPHIC,
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
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.width = 4

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        self.editor.add_to_scene(self.nexus)

        self.setPos(self._parent.x(), self._parent.y() + 100)
        self.update_nexus(self.pos())

    @property
    def parent(self) -> NODE_GRAPHIC:
        return self._parent

    @property
    def api_object(self) -> INJECTION_DEVICE_TYPES:
        return self._api_object

    def get_associated_graphics(self) -> List[GenericDiagramWidget | QGraphicsLineItem]:
        """
        Get a list of all associated graphics
        :return:
        """
        return [self.nexus]

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
        parent_pt = self.parent.get_nexus_point()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y(),
            parent_pt.x(),
            parent_pt.y(),
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

    def remove(self):
        """
        Remove this element
        @return:
        """
        # if ask:
        #     ok = yes_no_question(f'Are you sure that you want to remove this {self.device_type_name}?',
        #                          f'Remove {self.api_object.name}')
        # else:
        #     ok = True
        #
        # if ok:
        #     self.editor._remove_from_scene(self.nexus)
        #     self.editor.remove_element(device=self.api_object, graphic_object=self)
        #     self.editor._remove_from_scene(self)
        #     self.editor.delete_element_utility_function(device=self.api_object)

        self.editor.delete_with_dialogue(selected=[(self, self._api_object)], delete_from_db=False)

    def remove_from_widget_and_db(self, ask: bool = True, delete_from_db: bool = True) -> None:
        """
        Remove this element
        @return:
        """
        # if ask:
        #     ok = yes_no_question('Are you sure that you want to remove this device',
        #                          'Remove bus from schematic and DB' if delete_from_db else "Remove bus from schematic")
        # else:
        #     ok = True
        #
        # if ok:
        #     self.editor.remove_element(device=self.api_object,
        #                                 graphic_object=self,
        #                                 delete_from_db=delete_from_db)
        #
        #     self.editor._remove_from_scene(self.nexus)
        #     self.editor._remove_from_scene(self)
            # self.editor.delete_element_utility_function(device=self.api_object)

        self.editor.delete_with_dialogue(selected=[(self._api_object, self)], delete_from_db=False)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        self.editor.set_editor_model(api_object=self._api_object)

    def change_bus(self):
        """
        Change the generator bus
        """
        idx_bus_list = self.editor.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == self._api_object.bus:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
            elif idx_bus_list[1][1] == self._api_object.bus:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
            else:
                error_msg("The bus to change has not been selected!", 'Change bus')
                return

            ok = yes_no_question(
                text=f"Are you sure that you want to relocate the bus from {old_bus.name} to {new_bus.name}?",
                title='Change bus')

            if ok:
                self._api_object.bus = new_bus
                new_bus_graphic_item.add_object(api_obj=self._api_object)
                new_bus_graphic_item.update()
                self.editor.remove_element(device=self.api_object, graphic_object=self)

        else:
            warning_msg("you have to select the origin and destination buses!",
                        title='Change bus')

    def rescale(self, scale: float = 1.0):
        """

        :param scale:
        :return:
        """
        self.scale = scale
