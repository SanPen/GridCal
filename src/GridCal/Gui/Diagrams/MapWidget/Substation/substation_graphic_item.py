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
from typing import List, TYPE_CHECKING, Tuple
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication, QMenu, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate
from GridCal.Gui.GuiFunctions import add_menu_entry

from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem


class SubstationGraphicItem(QtWidgets.QGraphicsRectItem, NodeTemplate):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: Substation,
                 lat: float,
                 lon: float,
                 r: float = 20.0,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        """
        QtWidgets.QGraphicsRectItem.__init__(self)
        NodeTemplate.__init__(self,
                              api_object=api_object,
                              editor=editor,
                              draw_labels=draw_labels,
                              lat=lat,
                              lon=lon)

        self.editor: GridMapWidget = editor  # re assign for the types to be clear

        self.setRect(0.0, 0.0, r, r)
        self.lat = lat
        self.lon = lon

        if lat is not None and lon is not None:
            self.x, self.y = self.editor.to_x_y(lat=lat, lon=lon)
        else:
            self.x = 0
            self.y = 0

        self.radius = r

        self.resize(r)
        self.setAcceptHoverEvents(True)  # Enable hover events for the item
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)  # Allow selecting the node

        # Create a pen with reduced line width
        self.change_pen_width(0.5)

        # self.colorInner = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        # self.colorBorder = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        self.colorInner = QColor(255, 100, 100, 100)
        self.colorBorder = QColor(255, 100, 100, 100)

        # Assign color to the node
        self.setDefaultColor()
        self.hovered = False
        self.needsUpdate = False
        self.setZValue(1)
        self.voltage_level_graphics: List[VoltageLevelGraphicItem] = list()

    def register_voltage_level(self, vl: VoltageLevelGraphicItem):
        """

        :param vl:
        :return:
        """
        self.voltage_level_graphics.append(vl)

    def sort_voltage_levels(self) -> None:
        """
        Set the Zorder based on the voltage level voltage
        """
        # TODO: Check this
        sorted_objects = sorted(self.voltage_level_graphics, key=lambda x: x.api_object.Vnom)
        for i, vl_graphics in enumerate(sorted_objects):
            vl_graphics.setZValue(i)

    def updatePosition(self) -> None:
        """

        :return: 
        """
        real_position = self.pos()
        center_point = self.getPos()
        self.x = center_point.x() + real_position.x()
        self.y = center_point.y() + real_position.y()
        self.needsUpdate = True

    def updateDiagram(self):
        """
        
        :return: 
        """
        lat, long = self.editor.to_lat_lon(self.x, self.y)

        print(f'Updating SE position id:{self.api_object.idtag}, lat:{lat}, lon:{long}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def mouseMoveEvent(self, event):
        """
        Event handler for mouse move events.
        """

        if self.hovered:
            super().mouseMoveEvent(event)
            self.updatePosition()
            self.editor.update_connectors()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        self.editor.map.view.disableMove = True

        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists={
                                             DeviceType.CountryDevice: self.editor.circuit.get_countries(),
                                             DeviceType.CommunityDevice: self.editor.circuit.get_communities(),
                                             DeviceType.RegionDevice: self.editor.circuit.get_regions(),
                                             DeviceType.MunicipalityDevice: self.editor.circuit.get_municipalities(),
                                             DeviceType.AreaDevice: self.editor.circuit.get_areas(),
                                             DeviceType.ZoneDevice: self.editor.circuit.get_zones(),
                                         })

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse release events.
        """
        self.editor.disableMove = True
        self.updateDiagram()  # always update

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        self.setNodeColor(QColor(Qt.red), QColor(Qt.red))
        self.hovered = True
        QApplication.instance().setOverrideCursor(Qt.PointingHandCursor)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.setDefaultColor()
        QApplication.instance().restoreOverrideCursor()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="New",
                       icon_path="",
                       function_ptr=self.NewFunction)

        add_menu_entry(menu=menu,
                       text="Copy",
                       icon_path="",
                       function_ptr=self.CopyFunction)

        add_menu_entry(menu=menu,
                       text="Remove",
                       icon_path="",
                       function_ptr=self.RemoveFunction)

        menu.exec_(event.screenPos())

    def NewFunction(self):
        """
        Function to be called when Action 1 is selected.
        """
        # Implement the functionality for Action 1 here
        pass

    def CopyFunction(self):
        """
        Function to be called when Action 1 is selected.
        """
        # Implement the functionality for Action 1 here
        pass

    def RemoveFunction(self):
        """
        Function to be called when Action 1 is selected.
        """

        self.editor.removeSubstation(self)

        # Implement the functionality for Action 1 here
        pass

    def setNodeColor(self, inner_color: QColor = None, border_color: QColor = None) -> None:
        """

        :param inner_color:
        :param border_color:
        :return:
        """
        # Example: color assignment
        brush = QBrush(inner_color)
        self.setBrush(brush)

        if border_color is not None:
            pen = self.pen()
            pen.setColor(border_color)
            self.setPen(pen)

    def setDefaultColor(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.setNodeColor(self.colorInner, self.colorBorder)

    def getPos(self) -> QPointF:
        """

        :return:
        """
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def getRealPos(self) -> Tuple[float, float]:
        """

        :return:
        """
        self.updatePosition()
        return self.x, self.y

    def resize(self, new_radius: float) -> None:
        """
        Resize the node.
        :param new_radius: New radius for the node.
        """
        self.radius = new_radius
        self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
