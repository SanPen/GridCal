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

import logging

from PySide6.QtCore import Qt
from GridCal.Gui.Diagrams.MapWidget.Schema.segment import Segment
from GridCalEngine.Devices import LineLocation
from GridCalEngine.Devices.Diagrams.base_diagram import PointsGroup
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.enumerations import DeviceType

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

    def redraw_connectors_nodes(self):

        self.segments_list = list()

        diagram_locations: PointsGroup = self.editor.diagram.data.get(DeviceType.LineLocation.value, None)

        for elm in self.api_object.locations.data:

            if diagram_locations is None:
                # no locations found, use the data from the api object
                # lat = elm.lat
                # lon = elm.long
                pass
            else:

                # try to get location from the diagram
                diagram_location = diagram_locations.locations.get(elm.idtag, None)

                if diagram_location is None:
                    # no particular location found, use the data from the api object
                    # lat = elm.lat
                    # lon = elm.long
                    pass
                else:
                    # Draw only what's on the diagram
                    # diagram data found, use it
                    lat = diagram_location.latitude
                    lon = diagram_location.longitude

                    graphic_obj = self.editor.create_node(line_container=self,
                                                   api_object=elm,
                                                   lat=lat,  # 42.0 ...
                                                   lon=lon)  # 2.7 ...

                    nodSiz = self.number_of_nodes()

                    graphic_obj.index = nodSiz

                    if nodSiz > 1:
                        i1 = nodSiz - 1
                        i2 = nodSiz - 2
                        # Assuming Connector takes (scene, node1, node2) as arguments
                        segment_graphic_object = Segment(first=self.nodes_list[i1],
                                                         second=self.nodes_list[i2])

                        self.nodes_list[i1].needsUpdateFirst = True
                        self.nodes_list[i2].needsUpdateSecond = True
                        segment_graphic_object.needsUpdate=True

                        # register the segment in the line
                        self.add_segment(segment=segment_graphic_object)

                        # draw the segment in the scene
                        self.editor.add_to_scene(graphic_object=segment_graphic_object)

        self.update_connectors()

    def redraw_connectors(self):

        for segment in self.segments_list:
            self.editor.remove_from_scene(segment)

        self.segments_list = list()

        diagram_locations: PointsGroup = self.editor.diagram.data.get(DeviceType.LineLocation.value, None)

        id = 0

        for elm in self.api_object.locations.data:

            if diagram_locations is None:
                # no locations found, use the data from the api object
                # lat = elm.lat
                # lon = elm.long
                pass
            else:

                # try to get location from the diagram
                diagram_location = diagram_locations.locations.get(elm.idtag, None)

                if diagram_location is None:
                    # no particular location found, use the data from the api object
                    # lat = elm.lat
                    # lon = elm.long
                    pass
                else:
                    # Draw only what's on the diagram
                    # diagram data found, use it

                    if id > 0:
                        i1 = id
                        i2 = id - 1
                        # Assuming Connector takes (scene, node1, node2) as arguments
                        segment_graphic_object = Segment(first=self.nodes_list[i1],
                                                         second=self.nodes_list[i2])

                        self.nodes_list[i1].needsUpdateFirst = True
                        self.nodes_list[i2].needsUpdateSecond = True
                        segment_graphic_object.needsUpdate=True

                        # register the segment in the line
                        self.add_segment(segment=segment_graphic_object)

                        # draw the segment in the scene
                        self.editor.add_to_scene(graphic_object=segment_graphic_object)

                    id = id + 1

        self.update_connectors()

    def create_node(self, index):

        # Check if the index is valid
        if  (1 <= index < len(self.api_object.locations.data)):

            # Create a new API object for the node. Assuming `api_object.locations.data` holds coordinates or similar data
            new_api_node_data = self.api_object.locations.data[index]

            new_api_node_data.lat = (self.api_object.locations.data[index - 1].lat + self.api_object.locations.data[index].lat) / 2
            new_api_node_data.long = (self.api_object.locations.data[index -1].long + self.api_object.locations.data[index].long) / 2

            new_api_object = LineLocation(lat = new_api_node_data.lat,
                                          lon=new_api_node_data.long,
                                          z=new_api_node_data.alt,
                                          seq=new_api_node_data.seq,
                                          name=new_api_node_data.name,
                                          idtag=new_api_node_data.idtag,
                                          code=new_api_node_data.code
                                          )

            self.api_object.locations.data.insert(index, new_api_object)

            # Create a new graphical node item

            new_node = self.editor.create_node(self,new_api_object,new_api_object.lat,new_api_object.long)

            new_node.index = index

            id = 0

            for nod in self.nodes_list:

                if id >= index:

                    nod.index = nod.index + 1

                    id = id + 1

            # Add the node to the nodes list
            self.nodes_list.insert(index, new_node)

            # Update connectors if necessary
            self.redraw_connectors()

            # Return the newly created node
            return new_node

        else:

            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

            logging.info("Invalid node index")

    def split_Line(self, index):
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

            self.disableLine()

            return first_list, second_list
        else:
            # Handle invalid index
            raise ValueError("Index out of range or invalid")


    def disableLine(self):
        self.enabled = False
        for node in self.nodes_list:
            node.enabled=False
        for line in self.segments_list:
            line.set_line_color(Qt.gray)



