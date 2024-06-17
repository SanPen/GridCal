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
from typing import Dict, List, Tuple, Union
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class GraphicLocation:
    """
    GraphicLocation
    """

    def __init__(self,
                 x: int = 0,
                 y: int = 0,
                 h: int = 80,
                 w: int = 80,
                 r: float = 0,
                 poly_line: Union[None, List[Tuple[int, int]]] = None,
                 draw_labels: bool = True,
                 api_object: ALL_DEV_TYPES = None):
        """
        GraphicLocation
        :param x: x position (px)
        :param y: y position (px)
        :param h: height (px)
        :param w: width (px)
        :param r: rotation (deg)
        :param poly_line: List of poits to represent a polyline, if this object is to use one
        :param draw_labels: Draw labels?
        :param api_object: object to be linked to this representation
        """
        self.x = x
        self.y = y
        self.h = h
        self.w = w
        self.r = r
        self.poly_line = list() if poly_line is None else poly_line
        self.draw_labels = draw_labels
        self.api_object = api_object

    def get_properties_dict(self) -> Dict[str, Union[int, str]]:
        """
        get as a dictionary point
        :return:
        """
        return {'x': self.x,
                'y': self.y,
                'h': self.h,
                'w': self.w,
                'r': self.r,
                'poly_line': self.poly_line,
                'draw_labels': self.draw_labels,
                'api_object': self.api_object.idtag if self.api_object else ''}
