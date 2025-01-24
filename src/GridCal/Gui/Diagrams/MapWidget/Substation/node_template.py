# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, TYPE_CHECKING, List, Callable
from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush

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
                 lat: float = 0.0,
                 lon: float = 0.0):
        """

        :param api_object: any GridCal device object
        :param editor: GridMapWidget
        :param draw_labels:
        :param lat:
        :param lon:
        """
        GenericDiagramWidget.__init__(self,
                                      parent=None,
                                      api_object=api_object,
                                      editor=editor,
                                      draw_labels=draw_labels)

        self.lat = lat
        self.lon = lon

        self.hovered = False
        self.needsUpdate = False

        self._callbacks: List[Callable[[float, float], None]] = list()

    def add_position_change_callback(self, fcn: Callable[[float, float], None]):
        """
        Add callable function
        :param fcn: Function that accepts two floats (x, y) to update the positions
        :return:
        """
        self._callbacks.append(fcn)

    def set_callbacks(self, x: float, y: float) -> None:
        """
        Call all callback functions with x, y
        :param x: x position
        :param y: y position
        """
        for fcn in self._callbacks:
            fcn(x, y)

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

    def setBrush(self, brush: QBrush):
        """
        Dummy placeholder function
        :param brush:
        :return:
        """
        pass
