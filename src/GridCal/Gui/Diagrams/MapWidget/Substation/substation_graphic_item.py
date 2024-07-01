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
from PySide6.QtGui import QBrush, QColor, QPen, QCursor
# from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCal.Gui.Diagrams.TemplateWidgets.terminal_item import RoundMapTerminalItem
from GridCal.Gui.GuiFunctions import add_menu_entry

from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem


class SubstationGraphicItem(GenericDiagramWidget, QtWidgets.QGraphicsRectItem):
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
                 r: float = 40.0,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        """

        GenericDiagramWidget.__init__(self,
                                      parent=None,
                                      api_object=api_object,
                                      editor=editor,
                                      draw_labels=draw_labels)
        QtWidgets.QGraphicsRectItem.__init__(self, None)

        self.editor: GridMapWidget = editor  # re assign for the types to be clear

        self.voltage_level_graphics: List[VoltageLevelGraphicItem] = list()

        self._terminal = RoundMapTerminalItem("t", parent=self, editor=self.editor)

        # shape the substation
        self.lat = lat
        self.lon = lon
        self.radius = 50
        x, y = self.editor.to_x_y(lat=lat, lon=lon)
        self.setRect(x - self.radius / 2, y - self.radius / 2, self.radius, self.radius)

        print(f"Created SE at x:{x}, y:{y}, lat:{lat}, lon:{lon}")

        self.colorInner = QColor(255, 100, 100, 100)
        self.colorBorder = QColor(255, 100, 100, 100)
        self.pen_width = 4
        self.setPen(QPen(self.colorInner, self.pen_width, self.style))
        self.setBrush(self.colorBorder)
        # self.setFlags(self.GraphicsItemFlag.ItemIsSelectable)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Assign color to the node
        # self.setDefaultColor()
        # self.hovered = False
        # self.setZValue(1)

    def get_terminal(self) -> RoundMapTerminalItem:
        """
        Get the terminal
        :return:
        """
        return self._terminal

    def valid_coordinates(self) -> bool:
        """
        Checks if the coordinates are different from 0, 0
        :return: ok?
        """
        return self.lon != 0.0 and self.lat != 0.0

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

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """
        pos = self.mapToParent(event.pos())
        x = int(pos.x() - self.rect().width() / 2)
        y = int(pos.y() - self.rect().height() / 2)
        self.setRect(x, y, self.rect().width(), self.rect().height())

        self._terminal.update()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        self.editor.map.view.disableMove = True
        #
        # if self.api_object is not None:
        #     self.editor.set_editor_model(api_object=self.api_object,
        #                                  dictionary_of_lists={
        #                                      DeviceType.CountryDevice: self.editor.circuit.get_countries(),
        #                                      DeviceType.CommunityDevice: self.editor.circuit.get_communities(),
        #                                      DeviceType.RegionDevice: self.editor.circuit.get_regions(),
        #                                      DeviceType.MunicipalityDevice: self.editor.circuit.get_municipalities(),
        #                                      DeviceType.AreaDevice: self.editor.circuit.get_areas(),
        #                                      DeviceType.ZoneDevice: self.editor.circuit.get_zones(),
        #                                  })

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse release events.
        """
        self.editor.map.view.disableMove = False

        self.lat, self.lon = self.editor.to_lat_lon(x=self.pos().x(),
                                                    y=self.pos().y())

        print(f'Updating SE position id:{self.api_object.idtag}, lat:{self.lat}, lon:{self.lon}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=self.lat,
                                           longitude=self.lon,
                                           graphic_object=self)

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

    def getPos(self) -> QPointF:
        """

        :return:
        """
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def resize(self, r: float) -> None:
        """
        Resize the node.
        :param r: New radius for the node.
        """
        self.radius = r
        # self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)
        self.setRect(0.0, 0.0, r, r)

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
