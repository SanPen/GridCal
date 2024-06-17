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
from typing import Dict, Union, Tuple
from GridCalEngine.Devices.Diagrams.base_diagram import BaseDiagram
from GridCalEngine.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.enumerations import DiagramType
from GridCalEngine.basic_structures import Logger


class MapDiagram(BaseDiagram):
    """
    MapDiagram
    """

    def __init__(self, idtag: Union[None, str] = None, name: str = '',
                 tile_source: str = '', start_level: int = 11,
                 longitude: float = -15.41, latitude: float = 40.11) -> None:
        """
        MapDiagram
        :param idtag: uuid
        :param name: name of the diagram
        :param tile_source: tiles' source
        :param start_level: zoom level
        """
        BaseDiagram.__init__(self, idtag=idtag, name=name, diagram_type=DiagramType.SubstationLineMap)

        self.tile_source = tile_source

        self.start_level = start_level

        self.longitude = longitude  # longitude

        self.latitude = latitude  # latitude

    def get_properties_dict(self) -> Dict[str, Union[str, int, float, Dict[str, Union[GraphicLocation, MapLocation]]]]:
        """
        get the properties dictionary to save
        :return: dictionary to serialize
        """
        data = super().get_properties_dict()
        data['tile_source'] = self.tile_source
        data['start_level'] = self.start_level
        data['longitude'] = self.longitude
        data['latitude'] = self.latitude
        return data

    def set_center(self) -> None:
        """
        Set the middle coordinates as diagram origin
        :return: Nothing
        """
        if len(self.data):
            self.longitude, self.latitude = self.get_middle_coordinates()

    def get_middle_coordinates(self) -> Tuple[float, float]:
        """
        Find the middle coordinates as diagram origin
        :return: Longitude and Latitude
        """
        lon = 0.0
        lat = 0.0
        count = 0
        for dev_tpe_str, points_group in self.data.items():
            for idtag, location in points_group.locations.items():
                lon += location.longitude
                lat += location.latitude
                count += 1

        if count > 0:
            lat /= count
            lon /= count

        return lon, lat

    def parse_data(self,
                   data: Dict[str, Dict[str, Dict[str, Union[int, float]]]],
                   obj_dict: Dict[str, Dict[str, ALL_DEV_TYPES]],
                   logger: Logger):
        """
        Parse file data ito this class
        :param data: json dictionary
        :param obj_dict: dictionary of circuit objects by type to fincd the api objects back from file loading
        :param logger: logger object
        """
        super().parse_data(data=data, obj_dict=obj_dict, logger=logger)

        self.tile_source = data.get('tile_source', '')
        self.start_level = data.get('start_level', 11)
        self.longitude = data.get('longitude', -15.41)
        self.latitude = data.get('latitude', 40.11)
