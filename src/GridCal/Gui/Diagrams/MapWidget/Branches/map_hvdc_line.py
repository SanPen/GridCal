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
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapHvdcLine(MapLineContainer):

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: HvdcLine,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param draw_labels:
        """
        MapLineContainer.__init__(self, editor=editor, api_object=api_object, draw_labels=draw_labels)
