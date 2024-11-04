# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCalEngine.Devices.Branches.line import Line

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapAcLine(MapLineContainer):

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: Line,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param draw_labels:
        """
        MapLineContainer.__init__(self, editor=editor, api_object=api_object, draw_labels=draw_labels)
