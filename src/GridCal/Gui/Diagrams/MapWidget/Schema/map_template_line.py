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

from PySide6.QtCore import Qt
from GridCal.Gui.Diagrams.MapWidget.Schema.segment import Segment
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Devices.Branches.line import Line

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Schema.node_graphic_item import NodeGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapTemplateLine:
    """
    Represents a polyline in the map
    """
    def __init__(self, editor: GridMapWidget, api_object: BRANCH_TYPES):
        """

        :param editor:
        :param api_object:
        """
        # self.Parent = parent
        self.editor = editor
        self.api_object = api_object
        self.nodes_list = list()
        self.segments_list = list()
        self.enabled = True
        self.original = True

    def number_of_nodes(self) -> int:
        """

        :return:
        """
        return len(self.nodes_list)

    def add_node(self, node: NodeGraphicItem):
        """
        Add node
        :param node: NodeGraphicItem
        """
        self.nodes_list.append(node)

    def add_segment(self, segment: Segment):
        """
        Add segment
        :param segment: Connector
        """
        self.segments_list.append(segment)

    def update_connectors(self):
        """

        :return:
        """
        for conector in self.segments_list:
            conector.update_endings()

    def create_node(self):
        return 0

    def split_Line(self, index):
        """
        Split Line
        :param index:
        :return:
        """
        if 0 < index < len(self.api_object.locations.data) and len(self.api_object.locations.data) > 3:

            ln1 = Line()
            ln1.copyData(self.api_object)

            ln2 = Line()
            ln2.copyData(self.api_object)

            first_list = self.api_object.locations.data[:index]
            second_list = self.api_object.locations.data[index:]

            ln1.locations.data = first_list
            ln2.locations.data = second_list

            self.editor.create_line(ln1, diagram=self.editor.diagram, original=False)
            self.editor.create_line(ln2, diagram=self.editor.diagram, original=False)

            self.disable_line()

            return first_list, second_list
        else:
            # Handle invalid index
            raise ValueError("Index out of range or invalid")

    def disable_line(self):
        """

        :return:
        """
        self.enabled = False
        for node in self.nodes_list:
            node.enabled = False
        for line in self.segments_list:
            line.set_line_color(Qt.gray)



