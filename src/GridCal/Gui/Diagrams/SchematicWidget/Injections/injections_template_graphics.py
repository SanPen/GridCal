# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING, List
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsItemGroup, QMenu,
                               QGraphicsSceneContextMenuEvent)
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.generic_graphics import (GenericDiagramWidget, ACTIVE, DEACTIVATED, OTHER, Square, Circle,
                                                   Polygon, Condenser)

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
        self.glyph: Square | Circle | Polygon | Condenser | None = None
        self.scale = 1.0
        self.device_type_name = device_type_name

        # Properties of the container:
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.width = 4

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))


    def set_glyph(self, glyph: Square | Circle | Polygon | Condenser):
        """

        :param glyph:
        :return:
        """
        pen = QPen(self.color, self.width, self.style)
        self.glyph = glyph
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_nexus(self.pos())

        self._editor.add_to_scene(self.nexus)

    @property
    def parent(self) -> NODE_GRAPHIC:
        return self._parent

    @property
    def api_object(self) -> INJECTION_DEVICE_TYPES:
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        return self._editor

    def delete_from_associations(self):
        """
        Delete this object from the bus or other parent hosting it
        """
        self.parent.delete_child(self)

    def get_associated_widgets(self) -> List[GenericDiagramWidget | QGraphicsLineItem]:
        """
        Get a list of all associated graphics
        :return:
        """
        return list()

    def get_extra_graphics(self):
        """
        Get a list of all QGraphicsItem that are not GenericDiagramWidget elements associated with this widget.
        :return:
        """
        return [self.nexus, self.glyph]

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        pen = QPen(self.color, self.width, self.style)
        self.nexus.setPen(pen)
        self.glyph.setPen(pen)

        return pen

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

        self.glyph.setPen(QPen(self.color, self.width, self.style))

    def update_nexus(self, pos: QPointF):
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

    def delete(self):
        """
        Remove this element
        @return:
        """

        deleted, delete_from_db_final = self.editor.delete_with_dialogue(selected=[self], delete_from_db=False)


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
        self._editor.set_editor_model(api_object=self.api_object)

    def change_bus(self):
        """
        Change the generator bus
        """
        idx_bus_list = self._editor.get_selected_buses()

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
                self._editor.remove_element(device=self.api_object, graphic_object=self)

        else:
            warning_msg("you have to select the origin and destination buses!",
                        title='Change bus')

    def rescale(self, scale: float = 1.0):
        """

        :param scale:
        :return:
        """
        self.scale = scale

    def get_base_context_menu(self) -> QMenu:

        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Active",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.api_object.active)

        add_menu_entry(menu=menu,
                       text="Change bus",
                       function_ptr=self.change_bus,
                       icon_path=":/Icons/icons/move_bus.svg")

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       function_ptr=self.plot,
                       icon_path=":/Icons/icons/plot.svg")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       function_ptr=self.delete,
                       icon_path=":/Icons/icons/delete_schematic.svg")

        return menu

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = self.get_base_context_menu()

        menu.exec(event.screenPos())
