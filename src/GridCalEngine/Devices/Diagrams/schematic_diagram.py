# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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