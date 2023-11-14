# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import uuid
import networkx as nx
from typing import Dict, Union, List, Tuple
from GridCalEngine.Core.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.Core.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DiagramType, DeviceType


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

    def set_point(self, device: EditableDevice, location: Union[GraphicLocation, MapLocation]):
        """

        :param device:
        :param location:
        :return:
        """
        self.locations[device.idtag] = location

    def delete_device(self, device: EditableDevice) -> Union[object, None]:
        """
        Delete location
        :param device:
        :return:
        """
        loc = self.query_point(device)

        if loc:
            graphic_object = loc.graphic_object
            del self.locations[device.idtag]
            return graphic_object
        else:
            return None

    def query_point(self, device: EditableDevice) -> Union[GraphicLocation, MapLocation, None]:
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
                   obj_dict: Dict[str, EditableDevice]):
        """
        Parse file data ito this class
        :param data: json dictionary
        :param obj_dict: dicrtionary of relevant objects (idtag, object)
        """
        self.locations = dict()

        for idtag, location in data.items():

            if 'x' in location:
                self.locations[idtag] = GraphicLocation(x=location['x'],
                                                        y=location['y'],
                                                        w=location['w'],
                                                        h=location['h'],
                                                        r=location['r'],
                                                        api_object=obj_dict.get(idtag, None))
            if 'latitude' in location:
                self.locations[idtag] = MapLocation(latitude=location['latitude'],
                                                    longitude=location['longitude'],
                                                    altitude=location['altitude'],
                                                    api_object=obj_dict.get(idtag, None))


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

    def set_point(self, device: EditableDevice, location: Union[GraphicLocation, MapLocation]):
        """

        :param device:
        :param location:
        :return:
        """
        # check if the category exists ...
        d = self.data.get(device.device_type.value, None)

        if location.api_object is None:
            location.api_object = device

        if d is None:
            # the category does not exist, create it
            group = PointsGroup(name=device.device_type.value)
            group.set_point(device, location)
            self.data[device.device_type.value] = group
        else:
            # the category does exists, add point
            d.set_point(device, location)  # the category, exists, just add

    def delete_device(self, device: EditableDevice) -> Union[object, None]:
        """

        :param device:
        :return:
        """
        if device is not None:
            # check if the category exists ...
            d = self.data.get(device.device_type.value, None)

            if d:
                # the category does exist, delete from it
                return d.delete_device(device=device)
            else:
                # not found so we're ok
                return None
        else:
            return None

    def query_point(self, device: EditableDevice) -> Union[GraphicLocation, MapLocation, None]:
        """

        :param device:
        :return:
        """
        # check if the category exists ...
        group = self.data.get(device.device_type.value, None)

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
                   obj_dict: Dict[str, Dict[str, EditableDevice]]):
        """
        Parse file data ito this class
        :param data: json dictionary
        :param obj_dict: dictionary of circuit objects by type to fincd the api objects back from file loading
        """
        self.data = dict()

        self.name = data['name']

        self.diagram_type = DiagramType(data['type'])

        for category, loc_dict in data['data'].items():

            points_group = PointsGroup(name=category)
            points_group.parse_data(data=loc_dict, obj_dict=obj_dict.get(category, dict()))
            self.data[category] = points_group

    def build_graph(self) -> Tuple[nx.DiGraph, List[Bus]]:
        """
        Returns a networkx DiGraph object of the grid.
        return DiGraph, List[BusGraphicObject
        """
        graph = nx.DiGraph()

        bus_dictionary = dict()

        buses_groups = self.data.get(DeviceType.BusDevice.value, None)
        buses = list()
        if buses_groups:
            for i, (idtag, location) in enumerate(buses_groups.locations.items()):
                graph.add_node(i)
                bus_dictionary[idtag] = i
                buses.append(location.api_object)

            # branch_groups = dict()
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
                        f = bus_dictionary[branch.bus_from.idtag]
                        t = bus_dictionary[branch.bus_to.idtag]

                        if hasattr(branch, 'X'):
                            w = branch.X
                        else:
                            w = 1e-6

                        # self.graph.add_edge(f, t)
                        tuples.append((f, t, w))

            graph.add_weighted_edges_from(tuples)

        return graph, buses
