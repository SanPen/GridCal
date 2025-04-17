# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPen, QIcon, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Polygon, Square
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.Devices.Injections.load import Load

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class LoadGraphicItem(InjectionTemplateGraphicItem):

    def __init__(self, parent, api_obj: Load, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='load',
                                              w=20,
                                              h=20)

        # triangle
        self.set_glyph(glyph=Polygon(self,
                                     polygon=QPolygonF([QPointF(0, 0),
                                                        QPointF(self.w, 0),
                                                        QPointF(self.w / 2, self.h)]),
                                     update_nexus_fcn=self.update_nexus)
                       )

    @property
    def api_object(self) -> Load:
        return self._api_object
