# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING

from VeraGrid.Gui.Diagrams.generic_graphics import Square
from VeraGridEngine.Devices.Injections.external_grid import ExternalGrid
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class ExternalGridGraphicItem(InjectionTemplateGraphicItem):
    """
    ExternalGrid graphic item
    """

    def __init__(self, parent, api_obj: ExternalGrid, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='external grid',
                                              w=40,
                                              h=40)
        self.set_glyph(glyph=Square(self, 40, 40, "E", self.update_nexus))

    @property
    def api_object(self) -> ExternalGrid:
        return self._api_object
