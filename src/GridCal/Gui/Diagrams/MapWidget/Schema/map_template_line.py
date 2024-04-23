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
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QPoint, QRectF, QRect
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QGraphicsLineItem, QGraphicsPathItem

from GridCal.Gui.Diagrams.MapWidget.Schema.segment import Segment
from GridCalEngine.Devices.types import BRANCH_TYPES

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Schema.node_graphic_item import NodeGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapTemplateLine:
    """
    Represents a polyline in the map
    """
    def __init__(self, editor: GridMapWidget, api_object: BRANCH_TYPES):
        """

        :param editor:
        :param api_object:
        """
        # self.Parent = parent
        self.editor = editor
        self.api_object = api_object
        self.nodes_list = list()
        self.segments_list = list()

    def number_of_nodes(self) -> int:
        """

        :return:
        """
        return len(self.nodes_list)

    def add_node(self, node: NodeGraphicItem):
        """
        Add node
        :param node: NodeGraphicItem
        """
        self.nodes_list.append(node)

    def add_segment(self, segment: Segment):
        """
        Add segment
        :param segment: Connector
        """
        self.segments_list.append(segment)

    def update_connectors(self):
        """

        :return:
        """
        for conector in self.segments_list:
            conector.update_endings()
