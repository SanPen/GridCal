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
A tile source that serves BlueMarble tiles from the internet.
"""

import math
from typing import Tuple
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles


class BlueMarbleTiles(Tiles):
    """
    An object to source internet tiles for pySlip.
    """

    def __init__(self,
                 tiles_dir='blue_marble_tiles',
                 http_proxy=None,
                 name: str = 'Blue Marble'):
        """
        Override the base class for these tiles.

        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        :param tiles_dir:
        :param http_proxy:
        """

        super().__init__(tile_set_name=name,
                         tile_set_short_name='BM Tiles',
                         tile_set_version='1.0',
                         levels=list(range(10)),
                         tile_width=256,
                         tile_height=256,
                         tiles_dir=tiles_dir,
                         max_lru=10000,
                         servers=['https://s3.amazonaws.com', ],
                         url_path='/com.modestmaps.bluemarble/{Z}-r{Y}-c{X}.jpg',
                         max_server_requests=2,
                         http_proxy=http_proxy,
                         attribution="© NASA Blue Marble, © OpenStreetMap contributors")

    def copy(self) -> "BlueMarbleTiles":
        """
        Copy of this object
        :return:
        """

        cpy = BlueMarbleTiles(tiles_dir=self.tiles_dir,
                              http_proxy=self.http_proxy,
                              name=self.tile_set_name)

        return cpy

    def Geo2Tile(self, longitude: float, latitude: float) -> Tuple[float, float]:
        """Convert geo to tile fractional coordinates for level in use.

        geo  tuple of geo coordinates (xgeo, ygeo)

        Note that we assume the point *is* on the map!

        Code taken from [https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """

        lat_rad = math.radians(latitude)
        n = 2.0 ** self.level
        xtile = (longitude + 180.0) / 360.0 * n
        ytile = ((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0) * n

        return xtile, ytile

    def Tile2Geo(self, x_tile: float, y_tile: float) -> Tuple[float, float]:
        """Convert tile fractional coordinates to geo for level in use.

        tile  a tupl;e (xtile,ytile) of tile fractional coordinates

        Note that we assume the point *is* on the map!

        Code taken from [https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """
        n = 2.0 ** self.level
        xgeo = x_tile / n * 360.0 - 180.0
        yrad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
        ygeo = math.degrees(yrad)

        return xgeo, ygeo
