# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.Diagrams.generic_graphics import Condenser
from GridCalEngine.Devices.Injections.shunt import Shunt

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


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
                                              w=15,
                                              h=30,
                                              glyph=Condenser(self, h=30, w=15))

    @property
    def api_object(self) -> Shunt:
        return self._api_object
