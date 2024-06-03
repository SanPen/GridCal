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

from GridCalEngine.Devices.Diagrams.base_diagram import BaseDiagram
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.enumerations import DiagramType


class SchematicDiagram(BaseDiagram):
    """
    Diagram
    """

    def __init__(self, idtag=None, name=''):
        """

        :param name: Diagram name
        """
        BaseDiagram.__init__(self, idtag=idtag, name=name, diagram_type=DiagramType.Schematic)

    def update_xy(self, api_object: ALL_DEV_TYPES, x: int, y: int) -> None:
        """
        Update the element xy position
        :param api_object: Any DB object
        :param x: x position in px
        :param y: y position in px
        """
        location = self.query_point(api_object)
        if location:
            location.x = x
            location.y = y