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
from typing import List, Tuple, Union
import numpy as np
import pandas as pd

from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import DeviceType


class LineLocation(EditableDevice):
    """
    Line location object
    """

    def __init__(self,
                 lat: float,
                 lon: float,
                 z: float,
                 seq: int = 0,
                 name: str = "",
                 idtag: Union[str, None] = None,
                 code: str = ""):
        """
        Constructor
        :param lat: Latitude (deg)
        :param lon: Longitude (deg)
        :param z: Altitude (m)
        :param seq: Sequential position
        :param name: Name
        :param idtag: unique identifyer
        :param code: secondary code
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.LineLocation)

        self.lat = lat
        self.long = lon
        self.alt = z
        self.seq = seq

    def __eq__(self, other: "LineLocation") -> bool:
        """
        Compare two
        :param other: LineLocation
        :return: bool
        """
        return (np.isclose(self.lat, other.lat) and
                np.isclose(self.long, other.long) and
                np.isclose(self.alt, other.alt) and
                np.isclose(self.seq, other.seq))


class LineLocations(EditableDevice):
    """
    LineLocations
    """

    def __init__(self,
                 name: str = "",
                 idtag: Union[str, None] = None,
                 code: str = ""):
        """
        Constructor
        :param name: Name
        :param idtag: unique identifyer
        :param code: secondary code
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.LineLocations)

        self.data: List[LineLocation] = list()

    def get_locations(self) -> List[LineLocation]:
        """
        Get list of LineLocation
        """
        return self.data

    def add(self, sequence: int, latitude: float, longitude: float, altitude: float = 0.0):
        """
        Append row to this object (very slow)
        :param sequence: Sequence of the point
        :param latitude: Latitude (deg)
        :param longitude: Longitude (deg)
        :param altitude: Altitude (m)
        """
        self.data.append(LineLocation(lat=latitude, lon=longitude, z=altitude, seq=sequence))

    def parse(self, data: List[Tuple[int, float, float, float]]):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if len(data) > 0:
            values = np.array(data)
            self.set(data=values)
        else:
            self.data = np.zeros((0, 4))

    def set(self, data: np.ndarray):
        """
        Parse Json data
        :param data: List of lists with (sequence, latitude, longitude, altitude)
        """
        if data.ndim == 2:
            if data.shape[1] == 4:
                self.data.clear()
                for sequence, latitude, longitude, altitude in data:
                    self.data.append(LineLocation(lat=latitude, lon=longitude, z=altitude, seq=sequence))
            else:
                raise ValueError('Locations data does not have exactly 3 columns')
        else:
            raise ValueError('Location data must be 2-dimensional: (n_points, 3)')

    def to_list(self) -> List[Tuple[int, float, float, float]]:
        """
        Convert data to list of lists for Json usage
        :return: List[Tuple[int, float, float, float]] -> [(sequence, latitude, longitude, altitude)]
        """

        return [(loc.seq, loc.lat, loc.long, loc.alt) for loc in self.data]

    def to_df(self) -> pd.DataFrame:
        """
        Convert data to DataFrame
        :return: DataFrame
        """
        return pd.DataFrame(data=self.to_list(), columns=["sequence", "latitude", "longitude", "altitude"])

    def __eq__(self, other: "LineLocations") -> bool:
        """
        Equality compare
        In this case we check that the numerical data is close enough
        :param other: LineLocations object
        :return: Close enough?
        """
        if len(self.data) != len(other.data):
            return False

        for a, b in zip(self.data, other.data):
            if a != b:
                return False
        return True

    def __str__(self) -> str:

        return f"{len(self.data)} locations"
