"""
A tile source that serves Stamen Toner tiles from the internet.

Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL.
"""

import math
from typing import Tuple
from GridCal.Gui.MapWidget.Tiles.tiles import Tiles


class StamenTonerTiles(Tiles):
    """An object to source internet tiles for pySlip."""

    def __init__(self, tiles_dir='stamen_toner_tiles', http_proxy=None):
        """Override the base class for these tiles.

        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        """

        super().__init__(TilesetName='Stamen Toner Tiles',
                         TilesetShortName='STMT Tiles',
                         TilesetVersion='1.0',
                         levels=list(range(17)),
                         tile_width=256,
                         tile_height=256,
                         tiles_dir=tiles_dir,
                         servers=['http://tile.stamen.com',
                                  ],
                         url_path='/toner/{Z}/{X}/{Y}.png',
                         max_server_requests=2,
                         max_lru=10000,
                         http_proxy=http_proxy)

    def Geo2Tile(self, xgeo: float, ygeo: float) -> Tuple[float, float]:
        """Convert geo to tile fractional coordinates for level in use.

        geo  tuple of geo coordinates (xgeo, ygeo)

        Note that we assume the point *is* on the map!

        Code taken from [http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """

        lat_rad = math.radians(ygeo)
        n = 2.0 ** self.level
        xtile = (xgeo + 180.0) / 360.0 * n
        ytile = ((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0) * n

        return xtile, ytile

    def Tile2Geo(self, xtile: float, ytile: float) -> Tuple[float, float]:
        """Convert tile fractional coordinates to geo for level in use.

        tile  a tupl;e (xtile,ytile) of tile fractional coordinates

        Note that we assume the point *is* on the map!

        Code taken from [http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """

        n = 2.0 ** self.level
        xgeo = xtile / n * 360.0 - 180.0
        yrad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        ygeo = math.degrees(yrad)

        return xgeo, ygeo
