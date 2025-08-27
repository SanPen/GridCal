# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, TYPE_CHECKING, Dict, Callable, List
from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush

from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_segment import MapLineSegment
from VeraGrid.Gui.Diagrams.generic_graphics import GenericDiagramWidget

from VeraGridEngine.Devices.types import ALL_DEV_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


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

        :param api_object: any VeraGrid device object
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

        self._hosting_connections: Dict[MapLineSegment, Callable[[float, float], None]] = dict()

    def add_position_change_callback(self, obj: MapLineSegment, fcn: Callable[[float, float], None]):
        """
        Add callable function
        :param fcn: Function that accepts two floats (x, y) to update the positions
        :return:
        """
        self._hosting_connections[obj] = fcn

    def set_callbacks(self, x: float, y: float) -> None:
        """
        Call all callback functions with x, y
        :param x: x position
        :param y: y position
        """
        for obj, fcn in self._hosting_connections.items():
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

    def delete_hosting_connection(self, graphic_obj: MapLineSegment):
        """
        Delete object graphically connected to the graphical bus
        :param graphic_obj: LineGraphicTemplateItem (or child of this)
        """
        if graphic_obj in self._hosting_connections.keys():
            del self._hosting_connections[graphic_obj]
        else:
            print(f'No such hosting connection for {graphic_obj}')

    def get_hosting_line_segments(self) -> List[MapLineSegment]:
        """
        Ger a list of the lines that are hosted here
        """
        return list(self._hosting_connections.keys())