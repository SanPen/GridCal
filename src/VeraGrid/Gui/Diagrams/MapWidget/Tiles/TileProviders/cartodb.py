# MIT License
#
# Copyright (c) 2018 Ross Wilson
# Copyright (c) 2024, Santiago Peñate Vera
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
A tile source that serves OpenStreetMap tiles from server(s).
"""
from __future__ import  annotations
import math
from typing import Tuple, List
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles


class CartoDbTiles(Tiles):
    """
    An object to source server tiles for pySlipQt.
    """

    def __init__(self, tiles_dir='open_street_map_tiles',
                 http_proxy=None,
                 tile_servers: List[str] | None = None,
                 url_path='/{Z}/{X}/{Y}.png',
                 name: str = 'Carto positron',
                 tile_set_short_name='CartoDb Dark Matter',
                 tile_set_version='1.0',
                 attribution="© CARTO, © OpenStreetMap contributors",
                 min_zoom: int = 0,
                 max_zoom: int = 22,
                 tile_width=256,
                 tile_height=256):
        """
        Override the base class for these tiles.
        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        :param tiles_dir: Tiles directory
        :param http_proxy: Proxy URL
        :param tile_servers: List of tile servers
        :param url_path: extra path to query the tiles
        :param name: Name of the tile set
        :param tile_set_short_name: Short name of the tile set
        :param tile_set_version: Version of the tile set
        :param attribution: Attribution string of the tile set
        :param min_zoom: Minimal zoom
        :param max_zoom: Maximum zoom (+1)
        :param tile_width: Width of the tile (px)
        :param tile_height: Height of the tile (px)
        """

        super().__init__(tile_set_name=name,
                         tile_set_short_name=tile_set_short_name,
                         tile_set_version=tile_set_version,
                         levels=[z for z in range(min_zoom, max_zoom)],
                         tile_width=tile_width,
                         tile_height=tile_height,
                         tiles_dir=tiles_dir,
                         servers=["https://basemaps.cartocdn.com/dark_all/"] if tile_servers is None else tile_servers,
                         url_path=url_path,
                         max_server_requests=2,
                         max_lru=10000,
                         http_proxy=http_proxy,
                         attribution=attribution)

        # get tile information into instance
        self.level = min(self.levels)
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = self.GetInfo(self.level)

    def copy(self) -> "CartoDbTiles":
        """
        Copy of this object
        :return: CartoDbTiles
        """
        cpy = CartoDbTiles(tiles_dir=self.tiles_dir,
                           http_proxy=self.http_proxy,
                           tile_servers=self.servers.copy(),
                           url_path=self.url_path,
                           name=self.tile_set_name,
                           tile_set_short_name=self.tile_set_short_name,
                           tile_set_version=self.tile_set_version,
                           attribution=self.attribution_string,
                           min_zoom=self.min_level,
                           max_zoom=self.max_level,
                           tile_width=self.tile_width,
                           tile_height=self.tile_height
                           )

        return cpy

    def Geo2Tile(self, longitude: float, latitude: float) -> Tuple[float, float]:
        """
        Convert geo to tile fractional coordinates for level in use.
        geo  tuple of geo coordinates (longitude, latitude)
        Note that we assume the point *is* on the map!
        Code taken from [https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]

        Lon./lat. to tile numbers:
        n = 2 ^ zoom
        x_tile = n * ((lon_deg + 180) / 360)
        y_tile = n * (1 - (log(tan(lat_rad) + sec(lat_rad)) / π)) / 2

        :return: This code returns the coordinate of the upper left point of the tile. (x_tile, y_tile)
        """
        lat_rad = math.radians(latitude)
        n = math.pow(2.0, self.level)
        x_tile = (longitude + 180.0) / 360.0 * n
        y_tile = ((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0) * n

        return x_tile, y_tile

    def Tile2Geo(self, x_tile: float, y_tile: float) -> Tuple[float, float]:
        """
        Convert tile fractional coordinates to geo for level in use.
        tile  a tuple (x_tile, y_tile) of tile fractional coordinates
        Note that we assume the point *is* on the map!
        Code taken from [https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]

        n = 2 ^ zoom
        lon_deg = x_tile / n * 360.0 - 180.0
        lat_rad = arctan(sinh(π * (1 - 2 * y_tile / n)))
        lat_deg = lat_rad * 180.0 / π

        This returns the NW-corner of the square.
        Use the function with x_tile+1 and/or y_tile+1 to get the other corners.
        With x_tile+0.5 & y_tile+0.5 it will return the center of the tile.

        :return: This code returns the coordinate of the upper left point of the tile. (longitude, latitude)
        """

        n = 2.0 ** self.level
        longitude = x_tile / n * 360.0 - 180.0
        y_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
        latitude = math.degrees(y_rad)

        return longitude, latitude
