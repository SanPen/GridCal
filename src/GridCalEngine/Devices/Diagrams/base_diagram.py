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

import sys
import uuid
import networkx as nx
from typing import Dict, Union, List, Tuple
from GridCalEngine.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DiagramType, DeviceType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class PointsGroup:
    """
    Diagram
    """

    def __init__(self, name: str = '') -> None:
        """

        :param name: Diagram name
        """
        self.name = name

        # device_type: {device uuid: {x, y, h, w, r}}
        self.locations: Dict[str, Union[GraphicLocation, MapLocation]] = dict()

    def set_point(self, device: ALL_DEV_TYPES, location: Union[GraphicLocation, MapLocation]):
        """

        :param device:
        :param location:
        :return:
        """
        self.locations[device.idtag] = location

    def delete_device(self, device: ALL_DEV_TYPES):
        """
        Delete location
        :param device:
        :return:
        """
        loc = self.query_point(device)

        if loc:
            del self.locations[device.idtag]
        else:
            return None

    def query_point(self, device: ALL_DEV_TYPES) -> Union[GraphicLocation, MapLocation, None]:
        """

        :param device:
        :return:
        """
        return self.locations.get(device.idtag, None)

    def get_dict(self) -> Dict[str, Union[GraphicLocation, MapLocation]]:
        """

        :return:
        """
        points = {idtag: location.get_properties_dict() for idtag, location in self.locations.items()}

        return points

    def parse_data(self,
                   data: Dict[str, Dict[str, Union[int, float, List[Tuple[float, float]]]]],
                   obj_dict: Dict[str, ALL_DEV_TYPES],
                   logger: Logger,
                   category: str = "") -> None:
        """
        Parse file data ito this class
        :param data: json dictionary
        :param obj_dict: dicrtionary of relevant objects (idtag, object)
        :param logger: Logger
        :param category: category
        """
        self.locations = dict()

        for idtag, location in data.items():

            api_object = obj_dict.get(idtag, None)

            if api_object is None:
                # locations with no API object are not created
                logger.add_error("Diagram location could not find API object",
                                 device_class=category,
                                 device=idtag,)
            else:
                if 'x' in location:
                    self.locations[idtag] = GraphicLocation(x=location['x'],
                                                            y=location['y'],
                                                            w=location['w'],
                                                            h=location['h'],
                                                            r=location['r'],
                                                            api_object=api_object)
                if 'latitude' in location:
                    self.locations[idtag] = MapLocation(latitude=location['latitude'],
                                                        longitude=location['longitude'],
                                                        altitude=location['altitude'],
                                                        api_object=api_object)


class BaseDiagram:
    """
    Diagram
    """

    def __init__(self, idtag: Union[str, None], name: str, diagram_type: DiagramType = DiagramType):
        """

        :param name: Diagram name
        """
        if idtag is None:
            self.idtag = uuid.uuid4().hex
        else:
            self.idtag = idtag.replace('_', '').replace('-', '')

        self.name = name

        # device_type: {device uuid: {x, y, h, w, r}}
        self.data: Dict[str, PointsGroup] = dict()

        self.diagram_type = diagram_type

    def set_point(self, device: ALL_DEV_TYPES, location: Union[GraphicLocation, MapLocation]):
        """

        :param device:
        :param location:
        :return:
        """
        # check if the category exists ...
        d = self.data.get(str(device.device_type.value), None)

        if location.api_object is None:
            location.api_object = device

        if d is None:
            # the category does not exist, create it
            group = PointsGroup(name=str(device.device_type.value))
            group.set_point(device, location)
            self.data[str(device.device_type.value)] = group
        else:
            # the category does exists, add point
            d.set_point(device, location)  # the category, exists, just add

    def delete_device(self, device: ALL_DEV_TYPES) -> Union[object, None]:
        """

        :param device:
        :return:
        """
        if device is not None:
            # check if the category exists ...
            d = self.data.get(str(device.device_type.value), None)

            if d:
                # the category does exist, delete from it
                return d.delete_device(device=device)
            else:
                # not found so we're ok
                return None
        else:
            return None

    def query_point(self, device: ALL_DEV_TYPES) -> Union[GraphicLocation, MapLocation, None]:
        """

        :param device:
        :return:
        """
        # check if the category exists ...
        group = self.data.get(str(device.device_type.value), None)

        if group is None:
            return None  # the category did not exist
        else:
            # search for the device idtag and return the location, if not found return None
            return group.query_point(device)

    def query_by_type(self, device_type: DeviceType) -> Union[PointsGroup, None]:
        """
        Query diagram by device type
        :param device_type: DeviceType
        :return: PointsGroup
        """
        # check if the category exists ...
        group = self.data.get(device_type.value, None)

        return group

    def get_properties_dict(self) -> Dict[str, Union[str, int, float, Dict[str,  Union[GraphicLocation, MapLocation]]]]:
        """
        get the properties dictionary to save
        :return: dictionary to serialize
        """
        data = {category: group.get_dict() for category, group in self.data.items()}

        return {'type': self.diagram_type.value,
                'idtag': self.idtag,
                'name': self.name,
                'data': data}

    def parse_data(self,
                   data: Dict[str, Dict[str, Dict[str, Union[int, float]]]],
                   obj_dict: Dict[str, Dict[str, ALL_DEV_TYPES]],
                   logger: Logger):
        """
        Parse file data ito this class
        :param data: json dictionary
        :param obj_dict: dictionary of circuit objects by type to fincd the api objects back from file loading
        :param logger: logger
        """
        self.data = dict()

        self.name = data['name']

        self.diagram_type = DiagramType(data['type'])

        for category, loc_dict in data['data'].items():

            points_group = PointsGroup(name=category)
            points_group.parse_data(data=loc_dict,
                                    obj_dict=obj_dict.get(category, dict()),
                                    logger=logger,
                                    category=category)
            self.data[category] = points_group

    def build_graph(self) -> Tuple[nx.DiGraph, List[Bus]]:
        """
        Returns a networkx DiGraph object of the grid.
        return DiGraph, List[BusGraphicObject
        """
        graph = nx.DiGraph()

        node_devices = list()  # buses + fluid nodes

        # Add buses ----------------------------------------------------------------------------------------------------
        n_bus = 0
        graph_node_dictionary = dict()
        buses_groups = self.data.get(DeviceType.BusDevice.value, None)
        if buses_groups:
            for i, (idtag, location) in enumerate(buses_groups.locations.items()):
                graph.add_node(i)
                graph_node_dictionary[idtag] = i
                node_devices.append(location.api_object)
                n_bus += 1

        # Add fluid nodes ----------------------------------------------------------------------------------------------
        fluid_node_groups = self.data.get(DeviceType.FluidNodeDevice.value, None)
        if fluid_node_groups:
            for i, (idtag, location) in enumerate(fluid_node_groups.locations.items()):
                graph.add_node(i)
                graph_node_dictionary[idtag] = i + n_bus

                if location.api_object.bus is not None:
                    # the electrical bus location is the same
                    graph_node_dictionary[location.api_object.bus.idtag] = i + n_bus

                node_devices.append(location.api_object)

        # Add the electrical branches ----------------------------------------------------------------------------------
        tuples = list()
        for dev_type in [DeviceType.LineDevice,
                         DeviceType.DCLineDevice,
                         DeviceType.HVDCLineDevice,
                         DeviceType.Transformer2WDevice,
                         DeviceType.VscDevice,
                         DeviceType.UpfcDevice]:

            groups = self.data.get(dev_type.value, None)

            if groups:
                for i, (idtag, location) in enumerate(groups.locations.items()):
                    branch = location.api_object
                    f = graph_node_dictionary[branch.bus_from.idtag]
                    t = graph_node_dictionary[branch.bus_to.idtag]

                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-6

                    tuples.append((f, t, w))

        # Add fluid branches -------------------------------------------------------------------------------------------
        for dev_type in [DeviceType.FluidPathDevice]:

            groups = self.data.get(dev_type.value, None)

            if groups:
                for i, (idtag, location) in enumerate(groups.locations.items()):
                    branch = location.api_object
                    f = graph_node_dictionary[branch.source.idtag]
                    t = graph_node_dictionary[branch.target.idtag]

                    w = 0.01

                    tuples.append((f, t, w))

        # add all the tuples
        graph.add_weighted_edges_from(tuples)

        return graph, node_devices

    def get_boundaries(self):
        """
        Get the graphic representation boundaries
        :return: min_x, max_x, min_y, max_y
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        # shrink selection only
        for tpe, group in self.data.items():
            for key, location in group.locations.items():
                x = location.x
                y = location.y
                max_x = max(max_x, x)
                min_x = min(min_x, x)
                max_y = max(max_y, y)
                min_y = min(min_y, y)

        return min_x, max_x, min_y, max_y
