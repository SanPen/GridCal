# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from VeraGridEngine.Devices.Branches.dc_line import DcLine

if TYPE_CHECKING:
    from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapDcLine(MapLineContainer):

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: DcLine,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param draw_labels:
        """
        MapLineContainer.__init__(self, editor=editor, api_object=api_object, draw_labels=draw_labels)

    @property
    def api_object(self) -> DcLine:
        return self._api_object