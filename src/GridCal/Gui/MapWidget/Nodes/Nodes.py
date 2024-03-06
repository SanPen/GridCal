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
        :param index:
        :param editor:
        :param r:
        :param x:
        :param y:
        """
        super().__init__()

        self.Parent = parent
        self.Radius = r
        self.setRect(x - r, y - r, r * 2, r * 2)
        # self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)  # Allow moving the node
        # self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)  # Allow selecting the node
        parent.addItem(self)