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
from typing import Tuple, TYPE_CHECKING
from PySide6.QtWidgets import QApplication, QMenu, QGraphicsSceneContextMenuEvent
from GridCal.Gui.GuiFunctions import add_menu_entry
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QCursor

from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class NodeGraphicItem(QtWidgets.QGraphicsRectItem, NodeTemplate):
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
                 line_container: MapLineContainer,
                 api_object: LineLocation,
                 lat: float,
                 lon: float,
                 index: int,
                 r: float = 0.006,
                 draw_labels: bool = True):
        """

        :param editor:
        :param line_container:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        :param draw_labels:
        """
        QtWidgets.QGraphicsRectItem.__init__(self)
        NodeTemplate.__init__(self,
                              api_object=api_object,
                              editor=editor,
                              draw_labels=draw_labels,
                              lat=lat,
                              lon=lon)

        self.lat = lat
        self.lon = lon
        self.x, self.y = editor.to_x_y(lat=lat, lon=lon)
        self.radius = r
        self.draw_labels = True

        # self.editor: GridMapWidget = editor
        self.line_container: MapLineContainer = line_container
        # self.api_object: LineLocation = api_object
        self.index = index

        self.resize(r)
        self.setAcceptHoverEvents(True)  # Enable hover events for the item
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)  # Allow selecting the node

        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.hovered = False
        self.enabled = True
        self.itemSelected = False

        # Create a pen with reduced line width
        self.change_pen_width(0.001)

        # self.colorInner = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        # self.colorBorder = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        self.colorInner = QColor(255, 100, 100, 100)
        self.colorBorder = QColor(255, 100, 100, 100)
        self.setZValue(1)

        # Assign color to the node
        self.setDefaultColor()

    def get_center_pos(self) -> QPointF:
        """

        :return:
        """
        x = self.rect().x() + self.rect().width() / 2
        y = self.rect().y() + self.rect().height() / 2
        return QPointF(x, y)

    def updateRealPos(self) -> None:
        """

        :return:
        """
        real_position = self.pos()
        center_point = self.getPos()
        self.x = center_point.x() + real_position.x()
        self.y = center_point.y() + real_position.y()

    def updatePosition(self):
        """

        :return:
        """

        if self.enabled:
            self.updateRealPos()
            self.needsUpdate = True
            self.line_container.update_connectors()

    def updateDiagram(self):
        """

        :return:
        """
        real_position = self.pos()
        center_point = self.getPos()

        lat, long = self.editor.to_lat_lon(x=center_point.x() + real_position.x(),
                                           y=center_point.y() + real_position.y())

        print(f'Updating node position id:{self.api_object.idtag}, lat:{lat}, lon:{long}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

        self.lat = lat
        self.lon = long

    def mouseMoveEvent(self, event):
        """
        Event handler for mouse move events.
        """
        if self.enabled:
            pos = self.mapToParent(event.pos())
            x = pos.x() - self.rect().width() / 2
            y = pos.y() - self.rect().height() / 2
            self.setRect(x, y, self.rect().width(), self.rect().height())
            self.set_callabacks(pos.x(), pos.y())

            if self.hovered and self.enabled:
                self.updatePosition()

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)

        if self.enabled:
            self.editor.map.view.disableMove = True
            if event.button() == Qt.RightButton:
                pass
            elif event.button() == Qt.LeftButton:
                self.selectItem()

    def mouseReleaseEvent(self, event):
        """
        Event handler for mouse release events.
        """
        super().mouseReleaseEvent(event)
        self.editor.disableMove = True
        self.updateDiagram()
        self.editor.map.view._scene.update()

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        self.editor.inItem = True
        self.hovered = True
        self.setNodeColor(QColor(Qt.red), QColor(Qt.red))
        QApplication.instance().setOverrideCursor(Qt.PointingHandCursor)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.editor.inItem = False
        self.hovered = False
        self.setDefaultColor()
        QApplication.instance().restoreOverrideCursor()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """
        Event handler for context menu events.
        :param event:
        :return:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Add",
                       icon_path="",
                       function_ptr=self.AddFunction)

        add_menu_entry(menu=menu,
                       text="Split",
                       icon_path="",
                       function_ptr=self.SplitFunction)

        add_menu_entry(menu=menu,
                       text="Merge",
                       icon_path="",
                       function_ptr=self.MergeFunction)

        add_menu_entry(menu=menu,
                       text="Remove",
                       icon_path="",
                       function_ptr=self.RemoveFunction)

        menu.exec_(event.screenPos())

    def selectItem(self):
        """

        :return:
        """
        if not self.itemSelected:
            self.editor.map.view.selectedItems.append(self)
            self.setNodeColor(QColor(Qt.yellow), QColor(Qt.yellow))
        self.itemSelected = True

    def deSelectItem(self):
        """

        :return:
        """
        self.itemSelected = False
        self.setDefaultColor()

    def AddFunction(self):
        """

        :return:
        """
        self.line_container.insert_new_node_at_position(index=self.index)
        # Implement the functionality for Action 1 here
        pass

    def SplitFunction(self):
        """

        :return:
        """
        self.line_container.split_Line(index=self.index)
        # Implement the functionality for Action 1 here
        pass

    def RemoveFunction(self):
        """

        :return:
        """
        # Implement the functionality for Action 1 here
        self.editor.removeNode(self)

    def MergeFunction(self):
        """

        :return:
        """
        self.editor.merge_lines()
        pass

    def setNodeColor(self, inner_color: QColor, border_color: QColor = None) -> None:
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
        if self.itemSelected:
            self.setNodeColor(QColor(Qt.yellow), QColor(Qt.yellow))
        else:
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
        self.updateRealPos()
        return self.x, self.y

    def resize(self, new_radius: float):
        """
        Resize the node.
        :param new_radius: New radius for the node.
        """
        self.radius = new_radius
        self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)

    def change_pen_width(self, width: int):
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
