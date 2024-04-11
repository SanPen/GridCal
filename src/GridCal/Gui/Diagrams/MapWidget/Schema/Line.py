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

from GridCal.Gui.Diagrams.MapWidget.Schema.Connector import Connector
from GridCal.Gui.Diagrams.MapWidget.Schema.Nodes import NodeGraphicItem


class Line:
    def __init__(self, parent):
        self.Parent = parent
        self.Nodes = list()
        self.ConnectorList = []

    def CreateConnector(self, i1, i2):
        maxLen = len(self.Nodes)
        if(i1 > -1 and i2 > -1 and i1 < maxLen and i2 < maxLen):
            con = Connector(self.Parent, self.Nodes[i1], self.Nodes[i2])  # Assuming Connector takes (scene, node1, node2) as arguments
            self.ConnectorList.append(con)

    def CreateNode(self, lat, long):
        node = NodeGraphicItem(self.Parent,0.005, lat * self.Parent.devX, long * self.Parent.devY)
        self.Nodes.append(node)



