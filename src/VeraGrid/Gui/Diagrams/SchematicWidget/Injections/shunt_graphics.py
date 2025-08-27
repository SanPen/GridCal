# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from VeraGrid.Gui.Diagrams.generic_graphics import Condenser
from VeraGridEngine.Devices.Injections.shunt import Shunt

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class ShuntGraphicItem(InjectionTemplateGraphicItem):

    def __init__(self, parent, api_obj: Shunt, editor: "SchematicWidget"):
        """

        :param parent:
        :param api_obj:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='generator',
                                              w=20,
                                              h=40)
        self.set_glyph(glyph=Condenser(self, h=self.h, w=self.w, update_nexus_fcn=self.update_nexus))

    @property
    def api_object(self) -> Shunt:
        return self._api_object
