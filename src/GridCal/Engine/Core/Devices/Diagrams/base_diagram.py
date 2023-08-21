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
from typing import Dict, Union
from GridCal.Engine.Core.Devices.Diagrams.graphic_location import GraphicLocation
from GridCal.Engine.Core.Devices.Diagrams.map_location import MapLocation
from GridCal.Engine.Core.Devices.editable_device import EditableDevice


class BaseDiagram:
    """
    Diagram
    """

    def __init__(self, idtag=None, name=''):
        """

        :param name: Diagram name
        """
        if idtag is None:
            self.idtag = uuid.uuid4().hex
        else:
            self.idtag = idtag.replace('_', '').replace('-', '')

        self.name = name

        # device_type: {device uuid: {x, y, h, w, r}}
        self.points: Dict[str, Dict[str, Union[GraphicLocation, MapLocation]]] = dict()

    def set_point(self, device: EditableDevice, location: Union[GraphicLocation, MapLocation]):
        """

        :param device:
        :param location:
        :return:
        """
        # check if the category exists ...
        d = self.points.get(device.device_type.value, None)

        if d is None:
            self.points[device.device_type.value] = {device.idtag: location}  # create dictionary
        else:
            d[device.idtag] = location  # the category, exists, just add

    def query_point(self, device: EditableDevice) -> Union[GraphicLocation, MapLocation, None]:
        """

        :param device:
        :return:
        """
        # check if the category exists ...
        d = self.points.get(device.device_type.value, None)

        if d is None:
            return None  # the category did not exist
        else:
            # search for the device idtag and return the location, if not found return None
            return d.get(device.idtag, None)

    def get_properties_dict(self) -> Dict[str, Dict[str, Union[GraphicLocation, MapLocation]]]:
        """

        :return:
        """
        points = {category: {idtag: location.get_properties_dict() for idtag, location in loc_dict.items()}
                  for category, loc_dict in self.points.items()}

        return {'type': 'BusBranchDiagram',
                'idtag': self.idtag,
                'name': self.name,
                'points': points}

    def parse_data(self, data: Dict[str, Dict[str, Dict[str, Union[int, float]]]]):
        """
        Parse file data ito this class
        :param data: json dictionary
        """
        self.points = dict()

        self.name = data['name']

        for category, loc_dict in data['points'].items():

            points = dict()

            for idtag, location in loc_dict.items():

                if 'x' in location:
                    points[idtag] = GraphicLocation(x=location['x'],
                                                    y=location['y'],
                                                    w=location['w'],
                                                    h=location['h'],
                                                    r=location['r'])
                if 'latitude' in location:
                    points[idtag] = MapLocation(latitude=location['latitude'],
                                                longitude=location['longitude'],
                                                altitude=location['altitude'])

            self.points[category] = points
