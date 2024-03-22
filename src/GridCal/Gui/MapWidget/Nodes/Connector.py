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
from PySide6.QtWidgets import QGraphicsScene, QGraphicsLineItem

from GridCal.Gui.MapWidget.Nodes.Nodes import NodeGraphicItem


class Connector(QGraphicsLineItem):
    def __init__(self, parent: QGraphicsScene, first: NodeGraphicItem, second: NodeGraphicItem):
        super().__init__()
        self.Parent = parent
        self.First = first
        self.Second = second
        self.Parent.addItem(self)
        self.update()

    def update(self):
        # Get the positions of the first and second objects
        first_pos = self.First.getPos()
        second_pos = self.Second.getPos()

        # Create a pen with reduced line width
        pen = QPen()
        pen.setWidth(0.5)  # Adjust the width as needed

        # Set the pen for the ellipse item
        self.setPen(pen)

        # Set the line's starting and ending points
        self.setLine(first_pos.x(), first_pos.y(), second_pos.x(), second_pos.y())