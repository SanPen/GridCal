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
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen,  QColor
from PySide6.QtWidgets import QGraphicsLineItem

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Schema.node_graphic_item import NodeGraphicItem


class Segment(QGraphicsLineItem):
    """
    Segment joining two NodeGraphicItem
    """
    def __init__(self, first: NodeGraphicItem, second: NodeGraphicItem):
        """
        Segment constructor
        :param first: NodeGraphicItem
        :param second: NodeGraphicItem
        """
        super().__init__()
        self.first = first
        self.second = second
        color = QColor(Qt.blue)
        self.set_line_color(color)
        self.update_endings()
        self.needsUpdate = True

    def set_line_color(self, color: QColor) -> None:
        """

        :param color:
        """
        pen = self.pen()
        if pen is None:
            pen = QPen()
        pen.setWidth(0.5)  # Adjust the width as needed
        pen.setColor(color)  # Set the color
        self.setPen(pen)

    def update_endings(self) -> None:
        """
        Update the endings of this segment
        """

        # Get the positions of the first and second objects
        if self.first.needsUpdateFirst or self.second.needsUpdateSecond:
            first_pos = self.first.getRealPos()
            second_pos = self.second.getRealPos()

            # Set the line's starting and ending points
            self.setLine(first_pos[0], first_pos[1], second_pos[0], second_pos[1])

            self.first.needsUpdateFirst = False
            self.second.needsUpdateSecond = False
