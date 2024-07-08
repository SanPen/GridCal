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
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsSceneMouseEvent, QGraphicsEllipseItem
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget

from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    from GridCal.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem


class VoltageLevelGraphicItem(GenericDiagramWidget, QGraphicsEllipseItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 parent: SubstationGraphicItem,
                 editor: GridMapWidget,
                 api_object: VoltageLevel,
                 r: float = 0.2,
                 draw_labels: bool = True):
        """

        :param parent:
        :param editor:
        :param api_object:
        :param r:
        :param draw_labels:
        """
        parent_center = parent.get_center_pos()
        GenericDiagramWidget.__init__(self,
                                      parent=parent,
                                      api_object=api_object,
                                      editor=editor,
                                      draw_labels=draw_labels)
        QGraphicsEllipseItem.__init__(self, parent_center.x(), parent_center.y(), r * api_object.Vnom, r * api_object.Vnom, parent)

        parent.register_voltage_level(vl=self)

        self.editor: GridMapWidget = editor  # to reinforce the type
        self.api_object: VoltageLevel = api_object  # to reinforce the type

        self.radius = r * api_object.Vnom
        print(f"VL created at x:{parent_center.x()}, y:{parent_center.y()}")

        self.setAcceptHoverEvents(True)  # Enable hover events for the item
        # self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)  # Allow selecting the node

        # Create a pen with reduced line width
        self.change_pen_width(0.5)

        # self.colorInner = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        # self.colorBorder = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        self.colorInner = QColor(50, 80, 175, 100)  # light blue
        self.colorBorder = QColor(36, 59, 131, 100)  # dark blue

        # Assign color to the node
        self.setNodeColor(inner_color=self.colorInner, border_color=self.colorBorder)
        self.hovered = False
        self.needsUpdate = False
        self.setZValue(0)

    def center_on_substation(self) -> None:
        """
        Centers the graphic item on the substation
        """
        parent_center = self.parent.get_center_pos()
        xc = parent_center.x() - self.rect().width() / 2
        yc = parent_center.y() - self.rect().height() / 2
        self.setRect(xc, yc, self.rect().width(), self.rect().height())

    def move_to_xy(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.setRect(x, y, self.rect().width(), self.rect().height())
        return x, y

    def updateDiagram(self) -> None:
        """

        :return:
        """
        real_position = self.pos()
        center_point = self.getPos()
        lat, long = self.editor.to_lat_lon(x=center_point.x() + real_position.x(),
                                           y=center_point.y() + real_position.y())

        print(f'Updating VL position id:{self.api_object.idtag}, lat:{lat}, lon:{long}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """
        # super().mouseMoveEvent(event)
        if self.hovered:
            self.parent.mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        self.editor.disableMove = True
        self.updateDiagram()  # always update

        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists={
                                             DeviceType.SubstationDevice: self.editor.circuit.get_substations(),
                                         })

    def mouseReleaseEvent(self, event):
        """
        Event handler for mouse release events.
        """
        super().mouseReleaseEvent(event)
        self.editor.disableMove = True

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        self.setNodeColor(QColor(Qt.red), QColor(Qt.red))
        self.hovered = True

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.setNodeColor(self.colorInner, self.colorBorder)

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

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
