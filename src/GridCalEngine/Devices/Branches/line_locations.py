# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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

        self.locations = None
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

    __slots__ = ("data")

    def __init__(self,
                 name: str = "",
                 idtag: Union[str, None] = None,
                 code: str = ""):
        """
        Constructor
        :param name: Name
        :param idtag: unique identifier
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

    def add(self, sequence: int, latitude: float, longitude: float, altitude: float = 0.0, idtag: str = ""):
        """
        Append row to this object (very slow)
        :param sequence: Sequence of the point
        :param latitude: Latitude (deg)
        :param longitude: Longitude (deg)
        :param altitude: Altitude (m)
        :param idtag: Known idtag
        """
        self.data.append(LineLocation(lat=latitude, lon=longitude, z=altitude, seq=sequence, idtag=idtag))

    def add_location(self, lat: float, long: float, alt: float = 0.0):
        """
        Add a location to the line
        :param lat: Latitude (deg)
        :param long: Longitude (deg)
        :param alt: Altitude (m)
        """
        sequence = len(self.data)
        self.add(sequence=sequence, latitude=lat, longitude=long, altitude=alt)

    def remove(self, loc: LineLocation):
        self.data.remove(loc)

    def parse(self, data: List[Union[Tuple[int, float, float, float], Tuple[int, float, float, float, str]]]):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if len(data) > 0:
            values = np.array(data)
            self.set(data=values)
        else:
            self.data = list()

    def set(self, data: np.ndarray):
        """
        Parse Json data
        :param data: List of lists with (sequence, latitude, longitude, altitude)
        """
        if data.ndim == 2:
            if data.shape[1] == 4:
                self.data.clear()
                for sequence, latitude, longitude, altitude in data:
                    self.data.append(LineLocation(lat=float(latitude),
                                                  lon=float(longitude),
                                                  z=float(altitude),
                                                  seq=int(float(sequence))))
            elif data.shape[1] == 5:
                self.data.clear()
                for sequence, latitude, longitude, altitude, idtag in data:
                    self.data.append(LineLocation(lat=float(latitude),
                                                  lon=float(longitude),
                                                  z=float(altitude),
                                                  seq=int(float(sequence)),
                                                  idtag=str(idtag)))
            else:
                raise ValueError('Locations data does not have exactly 3 columns')
        else:
            raise ValueError('Location data must be 2-dimensional: (n_points, 3)')

    def to_list(self) -> List[Tuple[int, float, float, float, str]]:
        """
        Convert data to list of lists for Json usage
        :return: List[Tuple[int, float, float, float]] -> [(sequence, latitude, longitude, altitude)]
        """

        return [(loc.seq, loc.lat, loc.long, loc.alt, loc.idtag) for loc in self.data]

    def to_df(self) -> pd.DataFrame:
        """
        Convert data to DataFrame
        :return: DataFrame
        """
        return pd.DataFrame(data=self.to_list(), columns=["sequence", "latitude", "longitude", "altitude", "idtag"])

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
