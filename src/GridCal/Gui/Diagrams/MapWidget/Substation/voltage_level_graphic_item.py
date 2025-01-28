# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QMenu, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent, QGraphicsEllipseItem)

from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCal.Gui.gui_functions import add_menu_entry

from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.bus import Bus

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
        QGraphicsEllipseItem.__init__(self,
                                      parent_center.x(),
                                      parent_center.y(),
                                      r * api_object.Vnom * 0.01,
                                      r * api_object.Vnom * 0.01,
                                      parent)

        parent.register_voltage_level(vl=self)

        self.editor: GridMapWidget = editor  # to reinforce the type

        self.api_object: VoltageLevel = api_object  # to reinforce the type

        self.radius = r * api_object.Vnom * 0.01

        self.setAcceptHoverEvents(True)  # Enable hover events for the item

        # Allow moving the node
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create a pen with reduced line width
        self.change_pen_width(0.5)
        # Create a pen with reduced line width
        se_color = self.api_object.substation.color if self.api_object.substation is not None else QColor("#3d7d95")
        self.color = QColor(se_color)
        self.color.setAlpha(128)
        self.hoover_color = QColor(se_color)
        self.hoover_color.setAlpha(180)
        self.border_color = QColor(se_color)  # No Alpha

        # self.colorInner = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        # self.colorBorder = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        self.colorInner = QColor(50, 80, 175, 100)  # light blue
        self.colorBorder = QColor(36, 59, 131, 100)  # dark blue

        # Assign color to the node
        self.set_color(inner_color=self.colorInner, border_color=self.colorBorder)
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

    def set_size(self, r: float):
        """

        :param r: radius in pixels
        :return:
        """
        # if r != self.radius:
        rect = self.rect()
        rect.setWidth(r)
        rect.setHeight(r)
        self.radius = r

        # change the width and height while keeping the same center
        r2 = r / 2
        new_x = rect.x() - r2
        new_y = rect.y() - r2

        # Set the new rectangle with the updated dimensions
        self.setRect(new_x, new_y, r, r)

    def update_position_at_the_diagram(self) -> None:
        """

        :return:
        """
        real_position = self.pos()
        center_point = self.getPos()
        lat, long = self.editor.to_lat_lon(x=center_point.x() + real_position.x(),
                                           y=center_point.y() + real_position.y())

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """
        if self.hovered:
            self.parent.mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        self.parent.mousePressEvent(event)
        self.editor.disableMove = True
        self.update_position_at_the_diagram()  # always update

        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse release events.
        """
        super().mouseReleaseEvent(event)
        self.parent.mouseReleaseEvent(event)
        self.editor.disableMove = True

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        # self.set_color(QColor(Qt.GlobalColor.red), QColor(Qt.GlobalColor.red))
        self.set_color(self.hoover_color, self.color)
        self.hovered = True

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.set_color(self.colorInner, self.colorBorder)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Add bus",
                       icon_path="",
                       function_ptr=self.add_bus)

        menu.exec_(event.screenPos())

    def set_color(self, inner_color: QColor = None, border_color: QColor = None) -> None:
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
        pen.setWidth(width)  # keep this and do not change to setWidthF
        self.setPen(pen)

    def add_bus(self):
        """
        Add bus
        """
        bus = Bus(name=f"Bus {self.api_object.name}",
                  Vnom=self.api_object.Vnom,
                  substation=self.parent.api_object,
                  voltage_level=self.api_object)

        self.editor.circuit.add_bus(obj=bus)

    def set_default_color(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.set_color(self.color, self.border_color)
