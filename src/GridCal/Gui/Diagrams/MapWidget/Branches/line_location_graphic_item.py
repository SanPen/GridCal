# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Tuple, TYPE_CHECKING
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent
from GridCal.Gui.gui_functions import add_menu_entry
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor

from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class LineLocationGraphicItem(QtWidgets.QGraphicsEllipseItem, NodeTemplate):
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
        QtWidgets.QGraphicsEllipseItem.__init__(self)
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

        self.line_container: MapLineContainer = line_container

        self.index = index

        self.resize(r * 10)
        self.setAcceptHoverEvents(True)  # Enable hover events for the item
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)  # Allow selecting the node

        # self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.hovered = False
        self.enabled = True

        # Create a pen with reduced line width
        self.change_pen_width(0)
        self.colorInner = QColor(100, 100, 100, 100)
        self.colorBorder = QColor(100, 100, 100, 100)
        self.setZValue(1)

        # Assign color to the node
        self.set_default_color()

    def get_center_pos(self) -> QPointF:
        """

        :return:
        """
        x = self.rect().x() + self.rect().width() / 2
        y = self.rect().y() + self.rect().height() / 2
        return QPointF(x, y)

    def update_real_pos(self) -> None:
        """

        :return:
        """
        real_position = self.pos()
        center_point = self.get_pos()
        self.x = center_point.x() + real_position.x()
        self.y = center_point.y() + real_position.y()

    def update_position(self) -> None:
        """

        :return:
        """

        if self.enabled:
            self.update_real_pos()
            self.needs_update = True
            self.line_container.update_connectors()

    def update_position_at_the_diagram(self) -> None:
        """
        This function updates the position of this graphical element in the diagram
        """
        real_position = self.pos()
        center_point = self.get_pos()

        self.lat, self.lon = self.editor.to_lat_lon(x=center_point.x() + real_position.x(),
                                                    y=center_point.y() + real_position.y())

        # print(f'Updating node position id:{self.api_object.idtag}, lat:{self.lat}, lon:{self.lon}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=self.lat,
                                           longitude=self.lon,
                                           graphic_object=self)

        print()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """
        if self.enabled:
            pos = self.mapToParent(event.pos())
            x = pos.x() - self.rect().width() / 2
            y = pos.y() - self.rect().height() / 2
            self.setRect(x, y, self.rect().width(), self.rect().height())
            self.set_callbacks(pos.x(), pos.y())

            if self.hovered and self.enabled:
                self.update_position()

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        if self.enabled:
            self.editor.map.view.disable_move = True
            if event.button() == Qt.MouseButton.RightButton:
                pass

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse release events.
        """
        super().mouseReleaseEvent(event)
        self.editor.disableMove = True
        self.update_position_at_the_diagram()

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        self.hovered = True
        self.setNodeColor(QColor(Qt.GlobalColor.red), QColor(Qt.GlobalColor.red))

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.set_default_color()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """
        Event handler for context menu events.
        :param event:
        :return:
        """
        menu = QMenu()

        # add_menu_entry(menu=menu,
        #                text="Merge",
        #                icon_path="",
        #                function_ptr=self.MergeFunction)
        #
        # add_menu_entry(menu=menu,
        #                text="Split",
        #                icon_path=":/Icons/icons/divide.svg",
        #                function_ptr=self.SplitFunction)

        add_menu_entry(menu=menu,
                       text="Delete",
                       icon_path=":/Icons/icons/delete.svg",
                       function_ptr=self.remove)

        menu.exec_(event.screenPos())

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

    def remove(self):
        """
        Remove
        """
        self.line_container.removeNode(node=self)


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

    def set_default_color(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.setNodeColor(self.colorInner, self.colorBorder)

    def get_pos(self) -> QPointF:
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
        self.update_real_pos()
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
