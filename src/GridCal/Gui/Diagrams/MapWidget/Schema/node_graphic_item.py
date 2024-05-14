# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QMenu
from GridCal.Gui.GuiFunctions import add_menu_entry
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCal.Gui.Diagrams.MapWidget.Schema.map_template_line import MapTemplateLine
from GridCal.Gui.Diagrams.MapWidget.Schema.node_template import NodeTemplate

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class NodeGraphicItem(NodeTemplate):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 editor: GridMapWidget,
                 line_container: MapTemplateLine,
                 api_object: LineLocation,
                 lat: float,
                 lon: float,
                 r: float = 0.006):
        """

        :param editor:
        :param line_container:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        """
        NodeTemplate.__init__(self=self,
                              editor=editor,
                              line_container=line_container,
                              api_object=api_object,
                              lat=lat,
                              lon=lon,
                              r=r)

        # self.lat = lat
        # self.lon = lon
        # x, y = editor.to_x_y(lat=lat, lon=lon)
        # self.x = x
        # self.y = y
        # self.radius = r
        # self.draw_labels = True
        #
        # self.editor: GridMapWidget = editor
        # self.line_container: MapTemplateLine = line_container
        # self.api_object: LineLocation = api_object
        # self.index = -1
        #
        # self.resize(r)
        # self.setAcceptHoverEvents(True)  # Enable hover events for the item
        # self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        # self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)  # Allow selecting the node
        #
        # # Create a pen with reduced line width
        # self.change_pen_width(0.001)
        #
        # # self.colorInner = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        # # self.colorBorder = QColor(100, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        #
        # self.colorInner = QColor(255, 100, 100, 100)
        # self.colorBorder = QColor(255, 100, 100, 100)
        #
        # # Assign color to the node
        # self.setDefaultColor()
        #
        # self.hovered = False
        # self.needsUpdateFirst = True
        # self.needsUpdateSecond = True
        # self.enabled = True

    def mousePressEvent(self, event):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)

        if self.enabled:
            self.editor.disableMove = True
            if event.button() == Qt.RightButton:
                menu = QMenu()

                add_menu_entry(menu=menu,
                               text="Add",
                               icon_path="",
                               function_ptr=self.AddFunction)

                add_menu_entry(menu=menu,
                               text="Split",
                               icon_path="",
                               function_ptr=self.SplitFunction)

                add_menu_entry(menu=menu,
                               text="Remove",
                               icon_path="",
                               function_ptr=self.RemoveFunction)

                menu.exec_(event.screenPos())

    def AddFunction(self):
        """
        Function to be called when Action 1 is selected.
        """
        self.line_container.create_node(index=self.index)
        # Implement the functionality for Action 1 here
        pass

    def SplitFunction(self):
        """
        Function to be called when Action 1 is selected.
        """
        self.line_container.split_Line(index=self.index)
        # Implement the functionality for Action 1 here
        pass

    def RemoveFunction(self):
        """
        Function to be called when Action 1 is selected.
        """
        # Implement the functionality for Action 1 here
        pass

