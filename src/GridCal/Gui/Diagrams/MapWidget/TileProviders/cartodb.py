"""
A tile source that serves OpenStreetMap tiles from server(s).
"""

import math
from typing import Tuple
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles


class CartoDbTiles(Tiles):
    """An object to source server tiles for pySlipQt."""

    def __init__(self, tiles_dir='open_street_map_tiles', http_proxy=None, tile_servers=None):
        """
        Override the base class for these tiles.

        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        :param tiles_dir:
        :param http_proxy:
        :param tile_servers:
        """

        super().__init__(TilesetName='CartoDb Dark Matter',
                         TilesetShortName='CartoDb Dark Matter',
                         TilesetVersion='1.0',
                         levels=list(range(17)),
                         tile_width=256,
                         tile_height=256,
                         tiles_dir=tiles_dir,
                         servers=[
                             "http://basemaps.cartocdn.com/dark_all/"
                             # http://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png
                         ] if tile_servers is None else tile_servers,
                         url_path='/{Z}/{X}/{Y}.png',
                         max_server_requests=2,
                         max_lru=10000,
                         http_proxy=http_proxy)
        # TODO: implement map wrap-around
        #        self.wrap_x = True
        #        self.wrap_y = False

        # get tile information into instance
        self.level = min(self.levels)
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = self.GetInfo(self.level)

    def Geo2Tile(self, xgeo: float, ygeo: float) -> Tuple[float, float]:
        """
        Convert geo to tile fractional coordinates for level in use.
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
