# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List, Tuple, Union
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class GraphicLocation:
    """
    GraphicLocation
    """

    def __init__(self,
                 x: float = 0,
                 y: float = 0,
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
        :param poly_line: List of points to represent a polyline, if this object is to use one
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
