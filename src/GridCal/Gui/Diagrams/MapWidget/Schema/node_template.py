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
from PySide6.QtWidgets import QApplication, QMenu
from GridCal.Gui.GuiFunctions import add_menu_entry
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor

from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCal.Gui.Diagrams.MapWidget.Schema.map_template_line import MapTemplateLine

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class NodeTemplate:
    """
    Node Template
    """

    def __init__(self,
                 needsUpdateFirst: bool = True,
                 needsUpdateSecond: bool = True,
                 lat: float = 0.0,
                 lon: float = 0.0):
        """
        """
        self.needsUpdateFirst: bool = needsUpdateFirst
        self.needsUpdateSecond: bool = needsUpdateSecond
        self.lat = lat
        self.lon = lon

    def valid_coordinates(self) -> bool:
        """
        Checks if the coordinates are different from 0, 0
        :return: ok?
        """
        return self.lon != 0.0 and self.lat != 0.0

    def getRealPos(self):
        return QPointF(0, 0)
