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
from typing import Union, TYPE_CHECKING
from PySide6.QtCore import QPointF

from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget

from GridCalEngine.Devices.types import ALL_DEV_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class NodeTemplate(GenericDiagramWidget):
    """
    Node Template
    """

    def __init__(self,
                 api_object: ALL_DEV_TYPES = None,
                 editor: Union[GridMapWidget, None] = None,
                 draw_labels: bool = True,
                 needsUpdate: bool = True,
                 lat: float = 0.0,
                 lon: float = 0.0):
        """
        """
        GenericDiagramWidget.__init__(self,
                                      parent=None,
                                      api_object=api_object,
                                      editor=editor,
                                      draw_labels=draw_labels)

        self.needsUpdate: bool = needsUpdate
        self.lat = lat
        self.lon = lon

    def valid_coordinates(self) -> bool:
        """
        Checks if the coordinates are different from 0, 0
        :return: ok?
        """
        return self.lon != 0.0 and self.lat != 0.0

    def getRealPos(self):
        """

        :return:
        """
        return QPointF(0, 0)
