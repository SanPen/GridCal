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
import numpy as np
from typing import List, TYPE_CHECKING
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QPoint, QRectF, QRect
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor, QAction
from GridCalEngine.Devices.Substation.substation import Substation

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class SubstationGraphicItem(QtWidgets.QGraphicsRectItem):
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
                 r: float = 20.0):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        """
        super().__init__()

        self.setRect(0.0, 0.0, r, r)
        self.lat = lat
        self.lon = lon
        x, y = editor.to_x_y(lat=lat, lon=lon)
        self.x = x
        self.y = y
        self.radius = r
        self.draw_labels = True

        self.editor: GridMapWidget = editor
        self.api_object: Substation = api_object

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

    def updatePosition(self):
        real_position = self.pos()
        center_point = self.getPos()
        self.x = center_point.x() + real_position.x()
        self.y = center_point.y() + real_position.y()
        self.needsUpdate = True
        self.updateDiagram()

    def updateDiagram(self):
        real_position = self.pos()
        center_point = self.getPos()
        lat, long = self.editor.to_lat_lon(x=center_point.x() + real_position.x(),
                                           y=center_point.y() + real_position.y())

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def mouseMoveEvent(self, event):
        """
        Event handler for mouse move events.
        """
        super().mouseMoveEvent(event)
        if self.hovered:
            self.updatePosition()
            self.editor.UpdateConnectors()

    def mousePressEvent(self, event):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        self.editor.disableMove = True
        if event.button() == Qt.RightButton:
            menu = QMenu()

            action1 = QAction("New")
            action1.triggered.connect(self.NewFunction)
            menu.addAction(action1)

            action2 = QAction("Copy")
            action2.triggered.connect(self.CopyFunction)
            menu.addAction(action2)

            action3 = QAction("Remove")
            action3.triggered.connect(self.RemoveFunction)
            menu.addAction(action3)

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
        # Implement the functionality for Action 1 here
        pass

    def mouseReleaseEvent(self, event):
        """
        Event handler for mouse release events.
        """
        super().mouseReleaseEvent(event)
        self.editor.disableMove = True

    def hoverEnterEvent(self, event):
        """
        Event handler for when the mouse enters the item.
        """
        self.setNodeColor(QColor(Qt.red), QColor(Qt.red))
        self.hovered = True
        QApplication.instance().setOverrideCursor(Qt.PointingHandCursor)

    def hoverLeaveEvent(self, event):
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.setDefaultColor()
        QApplication.instance().restoreOverrideCursor()

    def setNodeColor(self, inner_color=None, border_color=None):
        # Example: color assignment
        brush = QBrush(inner_color)
        self.setBrush(brush)

        if border_color is not None:
            pen = self.pen()
            pen.setColor(border_color)
            self.setPen(pen)

    def setDefaultColor(self):
        # Example: color assignment
        self.setNodeColor(self.colorInner, self.colorBorder)

    def getPos(self):
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def getRealPos(self):
        self.updatePosition()
        return self.x, self.y

    def resize(self, new_radius):
        """
        Resize the node.
        :param new_radius: New radius for the node.
        """
        self.radius = new_radius
        self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)

    def change_pen_width(self, width):
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
