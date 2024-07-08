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
from typing import TYPE_CHECKING, List, Union

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_segment import MapLineSegment
from GridCalEngine.Devices import LineLocation
from GridCalEngine.Devices.Diagrams.base_diagram import PointsGroup
from GridCalEngine.Devices.types import BRANCH_TYPES, FluidPath
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Substation.node_graphic_item import NodeGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapLineContainer(GenericDiagramWidget):
    """
    Represents a polyline in the map
    """

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: Union[BRANCH_TYPES, FluidPath],
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        """
        GenericDiagramWidget.__init__(self,
                                      parent=None,
                                      api_object=api_object,
                                      editor=editor,
                                      draw_labels=draw_labels)

        self.editor: GridMapWidget = editor  # re assign to make clear the editor type

        self.nodes_list: List[NodeGraphicItem] = list()
        self.segments_list: List[MapLineSegment] = list()
        self.enabled = True
        self.original = True

    def setWidthScale(self, val: float):
        """
        Set the width scale of the line
        :param val:
        """
        for segment in self.segments_list:
            pen = segment.pen()  # get the current pen
            pen.setWidthF(val * segment.width)  # Set the fractional thickness of the line
            segment.setPen(pen)  # Assign the pen to the line item

    def clean_segments(self) -> None:
        """
        Remove all segments from the scene
        """
        for segment in self.segments_list:
            self.editor.remove_only_graphic_element(segment)

        self.segments_list = list()

    def clean_nodes(self) -> None:
        """
        Remove all the nodes from the scene
        """
        for node in self.nodes_list:
            self.editor.remove_from_scene(node)

        self.nodes_list = list()

    def clean(self) -> None:
        """
        Clean all graphic elements from the scene
        """
        self.clean_segments()
        self.clean_nodes()

    def number_of_nodes(self) -> int:
        """

        :return:
        """
        return len(self.nodes_list)

    def register_new_node(self, node: NodeGraphicItem):
        """
        Add node
        :param node: NodeGraphicItem
        """
        self.nodes_list.append(node)

    def add_segment(self, segment: MapLineSegment):
        """
        Add segment
        :param segment: Connector
        """
        self.segments_list.append(segment)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle, tool_tip: str = '') -> None:
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :param tool_tip: tool tip text
        :return:
        """
        for segment in self.segments_list:
            segment.setPen(QPen(color, w, style))
            segment.setToolTip(tool_tip)
            # segment.setPen(Qt.NoPen)
            # segment.setBrush(color)

    def update_connectors(self) -> None:
        """

        :return:
        """
        for conector in self.segments_list:
            conector.update_endings()

    def end_update(self) -> None:
        """

        :return:
        """

        for conector in self.segments_list:
            conector.end_update()

    def draw_all(self) -> None:
        """

        :return:
        """
        self.clean()

        diagram_locations: PointsGroup = self.editor.diagram.data.get(DeviceType.LineLocation.value, None)

        # draw line locations
        for elm in self.api_object.locations.data:

            if diagram_locations is None:
                # no locations found, use the data from the api object
                # lat = elm.lat
                # lon = elm.long
                pass
            else:

                # try to get location from the diagram
                # We will not take the location of the element in the database because we want to keep...
                # ... the diagram separated from database
                # diagram_location = diagram_locations.locations.get(elm.idtag, None)

                # if diagram_location is None:
                #     # no particular location found, use the data from the api object
                #     # lat = elm.lat
                #     # lon = elm.long
                #     pass
                # else:
                #     # Draw only what's on the diagram
                #     # diagram data found, use it

                graphic_obj = self.editor.create_node(line_container=self,
                                                      api_object=elm,
                                                      lat=elm.lat,  # 42.0 ...
                                                      lon=elm.long,
                                                      index=self.number_of_nodes())  # 2.7 ...

                self.register_new_node(node=graphic_obj)

        # second pass: create the segments
        self.redraw_segments()

    def removeNode(self, node: NodeGraphicItem):
        """

        :param node:
        :return:
        """
        for seg in self.segments_list:
            if seg.first.api_object == node.api_object or seg.second.api_object == node.api_object:
                self.editor.map.diagram_scene.removeItem(seg)

        self.nodes_list.remove(node)

        for nod in self.nodes_list:
            if nod.index > node.index:
                nod.index = nod.index - 1

        self.redraw_segments()

    def redraw_segments(self) -> None:
        """
        Draw all segments in the line
        If there were previous segments, those are deleted
        """
        self.clean_segments()

        connection_elements: List[Union[NodeGraphicItem, SubstationGraphicItem, VoltageLevelGraphicItem]] = list()

        # add the substation from
        substation_from_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_from())
        if substation_from_graphics is not None:
            if substation_from_graphics.valid_coordinates():
                connection_elements.append(substation_from_graphics)
                substation_from_graphics.line_container = self

        # add all the intermediate positions
        connection_elements += self.nodes_list

        # add the substation to
        substation_to_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_to())
        if substation_to_graphics is not None:
            if substation_to_graphics.valid_coordinates():
                connection_elements.append(substation_to_graphics)
                substation_to_graphics.line_container = self

        # second pass: create the segments
        for i in range(1, len(connection_elements)):
            elm1 = connection_elements[i - 1]
            elm2 = connection_elements[i]
            # Assuming Connector takes (scene, node1, node2) as arguments
            segment_graphic_object = MapLineSegment(first=elm1,
                                                    second=elm2,
                                                    container=self)

            elm2.needsUpdate = True
            segment_graphic_object.needsUpdate = True

            # register the segment in the line
            self.add_segment(segment=segment_graphic_object)

            # draw the segment in the scene
            self.editor.add_to_scene(graphic_object=segment_graphic_object)

        self.update_connectors()

        self.editor.Update_widths()

    def substation_to(self):
        return self.editor.graphics_manager.query(elm=self.api_object.get_substation_to())

    def substation_from(self):
        return self.editor.graphics_manager.query(elm=self.api_object.get_substation_from())

    def insert_new_node_at_position(self, index: int):
        """
        Creates a new node in the list at the given position
        :param index:
        :return:
        """

        # Check if the index is valid
        if 1 <= index < len(self.api_object.locations.data) and len(self.api_object.locations.data) > 1:

            nd1 = self.nodes_list[index]
            nd2 = self.nodes_list[index - 1]

            # Create a new API object for the node. Assuming `api_object.locations.data` holds coordinates or similar data
            new_api_node_data = self.api_object.locations.data[index]

            new_lat = ((nd2.lat + nd1.lat) / 2)
            new_long = ((nd2.lon + nd1.lon) / 2)

            new_api_object = LineLocation(lat=new_lat,
                                          lon=new_long,
                                          z=new_api_node_data.alt,
                                          seq=new_api_node_data.seq,
                                          name=new_api_node_data.name,
                                          idtag=new_api_node_data.idtag,
                                          code=new_api_node_data.code)

            self.api_object.locations.data.insert(index, new_api_object)

            # Create a new graphical node item

            graphic_obj = self.editor.create_node(line_container=self,
                                                  api_object=new_api_object,
                                                  lat=new_api_object.lat,
                                                  lon=new_api_object.long,
                                                  index=index)

            idx = 0

            for nod in self.nodes_list:

                if idx >= index:
                    nod.index = nod.index + 1

                idx = idx + 1

            # Add the node to the nodes list
            self.nodes_list.insert(index, graphic_obj)

            graphic_obj.updatePosition()

            # Update connectors if necessary
            self.redraw_segments()

            # Return the newly created node
            return graphic_obj

        elif len(self.api_object.locations.data) == 0:

            substation_from_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_from())
            substation_to_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_to())

            nd1 = substation_from_graphics
            nd2 = substation_to_graphics

            new_lat = ((nd2.lat + nd1.lat) / 2)
            new_long = ((nd2.lon + nd1.lon) / 2)

            new_api_object = LineLocation(lat=new_lat,
                                          lon=new_long,
                                          z=0,
                                          seq=0,
                                          name="New node",
                                          idtag="",
                                          code="")

            self.api_object.locations.data.insert(0, new_api_object)

            # Create a new graphical node item

            graphic_obj = self.editor.create_node(line_container=self,
                                                  api_object=new_api_object,
                                                  lat=new_api_object.lat,
                                                  lon=new_api_object.long,
                                                  index=0)

            # Add the node to the nodes list
            self.nodes_list.insert(0, graphic_obj)

            graphic_obj.updatePosition()

            # Update connectors if necessary
            self.redraw_segments()

            # Return the newly created node
            return graphic_obj

        elif (0 == index or index >= len(self.api_object.locations.data) - 1):

            substation_from_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_from())
            substation_to_graphics = self.editor.graphics_manager.query(elm=self.api_object.get_substation_to())

            nd1 = substation_from_graphics
            nd2 = substation_to_graphics

            if index == 0:
                nd2 = self.nodes_list[0]

            if index >= len(self.nodes_list):
                nd1 = self.nodes_list[len(self.nodes_list) - 1]

            new_lat = ((nd2.lat + nd1.lat) / 2)
            new_long = ((nd2.lon + nd1.lon) / 2)

            new_api_object = LineLocation(lat=new_lat,
                                          lon=new_long,
                                          z=0,
                                          seq=0,
                                          name="New node",
                                          idtag="",
                                          code="")

            self.api_object.locations.data.insert(index, new_api_object)

            # Create a new graphical node item

            graphic_obj = self.editor.create_node(line_container=self,
                                                  api_object=new_api_object,
                                                  lat=new_api_object.lat,
                                                  lon=new_api_object.long,
                                                  index=index)

            idx = 0

            for nod in self.nodes_list:

                if idx >= index:
                    nod.index = nod.index + 1

                idx = idx + 1

            # Add the node to the nodes list
            self.nodes_list.insert(index, graphic_obj)

            graphic_obj.updatePosition()

            # Update connectors if necessary
            self.redraw_segments()

            # Return the newly created node
            return graphic_obj

        else:

            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

            logging.info("Invalid node index")

    def split_Line(self, index):
        """
        Split Line
        :param index:
        :return:
        """
        if 0 < index < len(self.api_object.locations.data) and len(self.api_object.locations.data) > 3:

            ln1 = Line()
            ln1.copyData(self.api_object)
            # ln1 = self.api_object.copy()

            ln2 = Line()
            ln2.copyData(self.api_object)

            first_list = self.api_object.locations.data[:index]
            second_list = self.api_object.locations.data[index:]

            ln1.locations.data = first_list
            ln2.locations.data = second_list

            idx = 0
            for api_obj in first_list:
                api_obj.lat = self.nodes_list[idx].lat
                api_obj.long = self.nodes_list[idx].lon
                idx = idx + 1

            for api_obj in second_list:
                api_obj.lat = self.nodes_list[idx].lat
                api_obj.long = self.nodes_list[idx].lon
                idx = idx + 1

            l1 = self.editor.add_api_line(ln1, original=False)
            l2 = self.editor.add_api_line(ln2, original=False)

            self.disable_line()

            return first_list, second_list
        else:
            # Handle invalid index
            raise ValueError("Index out of range or invalid")

    def merge_line(self):
        return 0

    def disable_line(self):
        """

        :return:
        """
        self.enabled = False
        for node in self.nodes_list:
            node.enabled = False

        for line in self.segments_list:
            line.set_enable(val=False)
