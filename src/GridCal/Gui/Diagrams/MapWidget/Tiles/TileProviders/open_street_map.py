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

import math
from typing import Tuple
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles


class OsmTiles(Tiles):
    """An object to source server tiles for pySlipQt."""

    def __init__(self, name: str = 'OpenStreetMap Tiles', tiles_dir='open_street_map_tiles', http_proxy=None, tile_servers=None):
        """

        :param name:
        :param tiles_dir:
        :param http_proxy:
        :param tile_servers:
        """
        """Override the base class for these tiles.

        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        """

        super().__init__(TilesetName=name,
                         TilesetShortName='OSM Tiles',
                         TilesetVersion='1.0',
                         levels=list(range(20)),
                         tile_width=256,
                         tile_height=256,
                         tiles_dir=tiles_dir,
                         servers=[
                             # 'https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all',
                             'https://tile.openstreetmap.org',
                             # 'https://a.tile.openstreetmap.org',
                             # 'https://b.tile.openstreetmap.org',
                             # 'https://c.tile.openstreetmap.org',
                         ] if tile_servers is None else tile_servers,
                         url_path='/{Z}/{X}/{Y}.png',
                         max_server_requests=2,
                         max_lru=10000,
                         http_proxy=http_proxy,
                         attribution="© OpenStreetMap contributors")
        # TODO: implement map wrap-around
        #        self.wrap_x = True
        #        self.wrap_y = False

        # get tile information into instance
        self.level = min(self.levels)
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = self.GetInfo(self.level)

    def Geo2Tile(self, longitude: float, latitude: float) -> Tuple[int, int]:
        """
        Convert geo to tile fractional coordinates for level in use.
        geo  tuple of geo coordinates (xgeo, ygeo)
        Note that we assume the point *is* on the map!
        Code taken from [http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """
        lat_rad = math.radians(latitude)
        n = 2.0 ** self.level
        xtile = int((longitude + 180.0) / 360.0 * n)
        ytile = int(((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0) * n)

        return xtile, ytile

    def Tile2Geo(self, xtile: float, ytile: float) -> Tuple[float, float]:
        """
        Convert tile fractional coordinates to geo for level in use.
        tile  a tuple (xtile,ytile) of tile fractional coordinates
        Note that we assume the point *is* on the map!
        Code taken from [http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """

        n = 2.0 ** self.level
        xgeo = xtile / n * 360.0 - 180.0
        yrad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        ygeo = math.degrees(yrad)

        return xgeo, ygeo
