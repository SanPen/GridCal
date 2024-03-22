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
from typing import Union, TYPE_CHECKING
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPoint, QRectF, QRect
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor
from PySide6.QtWidgets import QMenu, QGraphicsSceneMouseEvent
import random

class NodeGraphicItem(QtWidgets.QGraphicsEllipseItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, parent=None, r: int = 20, x: int = 0, y: int = 0):
        """
        :param parent:
        :param r:
        :param x:
        :param y:
        """
        super().__init__()

        self.x = x
        self.y = y
        self.Parent = parent
        self.resize(r)
        # self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)  # Allow moving the node
        # self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)  # Allow selecting the node
        parent.addItem(self)

        # Create a pen with reduced line width
        self.change_pen_width(0.5)

        # Assign color to the node
        self.setNodeColor()

    def setNodeColor(self):
        # Example: Random color assignment
        color = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        brush = QBrush(color)
        self.setBrush(brush)

    def getPos(self):
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def resize(self, new_radius):
        """
        Resize the node.
        :param new_radius: New radius for the node.
        """
        self.Radius = new_radius
        self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)

    def change_pen_width(self, width):
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)