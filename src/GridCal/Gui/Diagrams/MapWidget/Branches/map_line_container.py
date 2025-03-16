# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import TYPE_CHECKING, List, Union

from PySide6.QtWidgets import QGraphicsItemGroup
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_segment import MapLineSegment
from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCalEngine.Devices.types import BRANCH_TYPES, FluidPath
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCal.Gui.messages import error_msg

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapLineContainer(GenericDiagramWidget, QGraphicsItemGroup):
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
        QGraphicsItemGroup.__init__(self)

        self.editor: GridMapWidget = editor  # reassign to make clear the editor type

        self.nodes_list: List[LineLocationGraphicItem] = list()
        self.segments_list: List[MapLineSegment] = list()
        self.enabled = True

    def set_width_scale(self, width: float, arrow_width: float):
        """
        Set the width scale of the line
        :param width:
        :param arrow_width:
        """
        for segment in self.segments_list:
            # pen = segment.pen()  # get the current pen
            # pen.setWidthF(val * segment.width)  # Set the fractional thickness of the line
            segment.set_width(width)  # Assign the pen to the line item
            segment.set_arrow_sizes(arrow_width)
        # self.setScale(branch_scale)

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

    def register_new_node(self, node: LineLocationGraphicItem):
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
        self.addToGroup(segment)

    def set_colour(self, color: QColor, style: Qt.PenStyle, tool_tip: str = '') -> None:
        """
        Set color and style
        :param color: QColor instance
        :param style: PenStyle instance
        :param tool_tip: tool tip text
        :return:
        """
        for segment in self.segments_list:
            segment.setToolTip(tool_tip)
            segment.set_colour(color=color, style=style)

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

        for segment in self.segments_list:
            segment.end_update()

    def draw_all(self) -> None:
        """

        :return:
        """
        self.clean()

        # get the diagram line locations
        line_locs_info = self.editor.diagram.query_by_type(device_type=DeviceType.LineLocation)

        # draw line locations
        for elm in self.api_object.locations.data:

            if line_locs_info is not None:
                loc_data = line_locs_info.locations.get(elm.idtag, None)
            else:
                loc_data = None

            graphic_obj = self.editor.create_line_location_graphic(line_container=self,
                                                                   api_object=elm,
                                                                   lat=elm.lat if loc_data is None else loc_data.latitude,
                                                                   lon=elm.long if loc_data is None else loc_data.longitude,
                                                                   index=self.number_of_nodes())  # 2.7 ...

            self.register_new_node(node=graphic_obj)

        # second pass: create the segments
        self.redraw_segments()

    def removeNode(self, node: LineLocationGraphicItem):
        """

        :param node:
        :return:
        """
        for seg in self.segments_list:
            if seg.first.api_object == node.api_object or seg.second.api_object == node.api_object:
                self.editor.map.diagram_scene.removeItem(seg)

        self.nodes_list.remove(node)
        self.api_object.locations.remove(node.api_object)

        for nod in self.nodes_list:
            if nod.index > node.index:
                nod.index = nod.index - 1

        self.editor.remove_line_location_graphic(node)
        self.redraw_segments()

    def redraw_segments(self) -> None:
        """
        Draw all segments in the line
        If there were previous segments, those are deleted
        """
        self.clean_segments()

        connection_elements: List[
            Union[LineLocationGraphicItem, SubstationGraphicItem, VoltageLevelGraphicItem]] = list()

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

        br_scale = self.editor.get_branch_width()
        arrow_scale = self.editor.get_arrow_scale()

        # second pass: create the segments
        for i in range(1, len(connection_elements)):
            elm1 = connection_elements[i - 1]
            elm2 = connection_elements[i]
            # Assuming Connector takes (scene, node1, node2) as arguments
            segment_graphic_object = MapLineSegment(first=elm1,
                                                    second=elm2,
                                                    container=self,
                                                    width=self.editor.diagram.min_branch_width)

            elm2.needsUpdate = True
            segment_graphic_object.needsUpdate = True

            # segment_graphic_object.set_width(br_scale * segment_graphic_object.width)  # Assign the pen to the line item
            # segment_graphic_object.set_arrow_sizes(arrow_scale)

            # register the segment in the line
            self.add_segment(segment=segment_graphic_object)

            # draw the segment in the scene
            self.editor.add_to_scene(graphic_object=segment_graphic_object)

        self.update_connectors()

        # self.editor.update_device_sizes()

    def substation_to(self):
        """

        :return:
        """
        return self.editor.graphics_manager.query(elm=self.api_object.get_substation_to())

    def substation_from(self):
        """

        :return:
        """
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
                                          idtag=None,  # generates new UUID
                                          code=new_api_node_data.code)

            self.api_object.locations.data.insert(index, new_api_object)

            # Create a new graphical node item

            graphic_obj = self.editor.create_line_location_graphic(line_container=self,
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

            graphic_obj.update_position()

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

            graphic_obj = self.editor.create_line_location_graphic(line_container=self,
                                                                   api_object=new_api_object,
                                                                   lat=new_api_object.lat,
                                                                   lon=new_api_object.long,
                                                                   index=0)

            # Add the node to the nodes list
            self.nodes_list.insert(0, graphic_obj)

            graphic_obj.update_position()

            # Update connectors if necessary
            self.redraw_segments()

            # Return the newly created node
            return graphic_obj

        elif 0 == index or index >= len(self.api_object.locations.data) - 1:

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

            graphic_obj = self.editor.create_line_location_graphic(line_container=self,
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

            graphic_obj.update_position()

            # Update connectors if necessary
            self.redraw_segments()

            # Return the newly created node
            return graphic_obj

        # else:
        #     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        #     logging.info("Invalid node index")

    def split_Line(self, index):
        """
        Split Line
        :param index:
        :return:
        """
        # TODO: Review this and possibly link to existing functions
        if 0 < index < len(self.api_object.locations.data) and len(self.api_object.locations.data) > 3:

            # ln1 = Line()
            # ln1.set_data_from(self.api_object)
            ln1 = self.api_object.copy()

            # ln2 = Line()
            # ln2.set_data_from(self.api_object)
            ln2 = self.api_object.copy()

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

            ln1.bus_from = self.api_object.bus_from
            ln2.bus_to = self.api_object.bus_to

            # l1 = self.editor.add_api_line(ln1, original=False)
            # l2 = self.editor.add_api_line(ln2, original=False)

            self.disable_line()

            return first_list, second_list
        else:
            # Handle invalid index
            error_msg("Index out of range or invalid", "split line")

    def disable_line(self):
        """

        :return:
        """
        self.enabled = False
        for node in self.nodes_list:
            node.enabled = False

        for line in self.segments_list:
            line.set_enable(val=False)

    def set_arrows_with_power(self, Sf: complex | None, St: complex | None) -> None:
        """

        :param Sf:
        :param St:
        :return:
        """
        for segment in self.segments_list:
            segment.set_arrows_with_power(Sf=Sf, St=St)

    def set_arrows_with_hvdc_power(self, Pf: float, Pt: float) -> None:
        """

        :param Pf:
        :param Pt:
        :return:
        """
        for segment in self.segments_list:
            segment.set_arrows_with_hvdc_power(Pf=Pf, Pt=Pt)

    def calculate_total_length(self) -> float:
        """
        Calculate the total length of the line by summing the distances between all waypoints
        using the haversine formula, and update the line's length property. Issue #23
        
        :return: Total length in kilometers
        """
        from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import haversine_distance
        
        # Get all connection points (substations and intermediate points)
        connection_points = []
        
        # Add the substation from
        substation_from = self.substation_from()
        if substation_from is not None:
            connection_points.append((substation_from.lat, substation_from.lon))
        
        # Add all intermediate points
        for node in self.nodes_list:
            connection_points.append((node.lat, node.lon))
        
        # Add the substation to
        substation_to = self.substation_to()
        if substation_to is not None:
            connection_points.append((substation_to.lat, substation_to.lon))
        
        # Calculate total length by summing distances between consecutive points
        total_length = 0.0
        for i in range(len(connection_points) - 1):
            lat1, lon1 = connection_points[i]
            lat2, lon2 = connection_points[i + 1]
            segment_length = haversine_distance(lat1, lon1, lat2, lon2)
            total_length += segment_length
        
        # Update the line's length property
        if total_length > 0.0:
            self.api_object.length = total_length
            
        return total_length
