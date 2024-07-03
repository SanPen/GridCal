"""
A base Tiles object for pySlipQt local tiles.

All tile sources should inherit from this base class.
For example, see gmt_local.py (local tiles) and osm_tiles.py
(internet tiles).
"""

import os
import math
from typing import Tuple, Union, List
from collections.abc import Callable
from PySide6.QtGui import QPixmap
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles_cache import TilesCache


class BaseTiles(object):
    """A base tile object to source local tiles for pySlip."""

    def __init__(self,
                 levels: List[int],
                 tile_width: int,
                 tile_height: int,
                 tiles_dir: str,
                 max_lru: int):
        """
        Initialise a Tiles instance.
        :param levels: a list of level numbers that are to be served
        :param tile_width: width of each tile in pixels
        :param tile_height: height of each tile in pixels
        :param tiles_dir: path to on-disk tile cache directory
        :param max_lru: maximum number of tiles cached in-memory
        """

        # save params
        self.levels = levels
        self.tile_size_x = tile_width
        self.tile_size_y = tile_height
        self.tiles_dir = tiles_dir
        self.max_lru = max_lru

        # set min and max tile levels and current level
        self._min_level = min(self.levels)
        self._max_level = max(self.levels)
        self.level = self.min_level

        self.num_tiles_x = 0
        self.num_tiles_y = 0
        self.ppd_x = 0
        self.ppd_y = 0

        # TODO: implement map wrap-around
        #        self.wrap_x = False
        #        self.wrap_y = False

        # setup the tile cache
        self.cache = TilesCache(tiles_dir=tiles_dir, max_lru=max_lru)

        #####
        # Now finish setting up
        #####

        # tiles extent for tile data (left, right, top, bottom)
        self.extent = (-180.0, 180.0, -85.0511, 85.0511)

        # check tile cache - we expect there to already be a directory
        if not os.path.isdir(tiles_dir):
            if os.path.isfile(tiles_dir):
                msg = ("%s doesn't appear to be a tile cache directory" % tiles_dir)
                raise Exception(msg) from None

            msg = "The tiles directory %s doesn't exist." % tiles_dir
            raise Exception(msg) from None

    @property
    def max_level(self):
        """

        :return:
        """
        return self._max_level

    @property
    def min_level(self):
        """

        :return:
        """
        return self._min_level

    @property
    def tile_width(self):
        """

        :return:
        """
        return self.tile_size_x

    @property
    def tile_height(self):
        """

        :return:
        """
        return self.tile_size_y

    @property
    def map_width(self):
        """

        :return:
        """
        return self.num_tiles_x * self.tile_width  # virtual map width

    @property
    def map_height(self):
        """

        :return:
        """
        return self.num_tiles_y * self.tile_height  # virtual map height

    @property
    def map_llon(self):
        """

        :return:
        """
        return self.extent[0]

    @property
    def map_rlon(self):
        """

        :return:
        """
        return self.extent[1]

    @property
    def map_blat(self):
        """

        :return:
        """
        return self.extent[2]

    @property
    def map_tlat(self):
        """

        :return:
        """
        return self.extent[3]

    def UseLevel(self, level):
        """Prepare to serve tiles from the required level.

        level  the required level

        Return True if level change occurred, else False if not possible.
        """

        # first, CAN we zoom to this level?
        if level not in self.levels:
            return False

        # get tile info
        info = self.GetInfo(level)
        if info is None:
            return False

        # OK, save new level
        self.level = level
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = info

        return True

    def GetTile(self, x: float, y: float) -> QPixmap:
        """Get bitmap for tile at tile coords (x, y) and current level.

        x  X coord of tile required (tile coordinates)
        y  Y coord of tile required (tile coordinates)

        Returns bitmap object for the tile image.
        Tile coordinates are measured from map top-left.
        """

        #        # if we are wrapping X or Y, get wrapped tile coords
        #        if self.wrap_x:
        #            x = (x + self.num_tiles_x*self.tile_size_x) % self.num_tiles_x
        #        if self.wrap_y:
        #            y = (y + self.num_tiles_y*self.tile_size_y) % self.num_tiles_y

        # retrieve the tile
        try:
            # get tile from cache
            return self.cache[(self.level, x, y)]
        except KeyError as e:
            raise KeyError("Can't find tile for key '%s'" % str((self.level, x, y))) from None

    def GetInfo(self, level: int) -> Union[Tuple[float, float, None, None], None]:
        """Get tile info for a particular level.

        level  the level to get tile info for

        Returns (num_tiles_x, num_tiles_y, ppd_x, ppd_y) or None if 'level'
        doesn't exist.

        Note that ppd_? may be meaningless for some tiles, so its
        value will be None.
        """

        # is required level available?
        if level not in self.levels:
            return None

        # otherwise get the information
        self.num_tiles_x = int(math.pow(2, level))
        self.num_tiles_y = int(math.pow(2, level))

        return self.num_tiles_x, self.num_tiles_y, None, None

    def GetExtent(self):
        """Get geo limits of the map tiles.
                         (min_lon,   max_lon,   min_lat,   max_lat)
        Returns a tuple: (min_geo_x, max_geo_x, min_geo_y, max_geo_y)
        """

        return self.extent

    def tile_on_disk(self, level: int, x: float, y: float):
        """
        Return True if tile at (level, x, y) is on-disk.
        """

        raise Exception('You must override BaseTiles.tile_on_disk(level, x, y))')

    def setCallback(self, callback: Callable[[int, float, float, QPixmap, bool], None]):
        """
        Set the "tile available" callback function.
        Only used with internet tiles.  See "tiles_net.py".
        """

        pass
        # raise Exception('You must override BaseTiles.setCallback(callback))')

    def Geo2Tile(self, longitude: float, latitude: float) -> Tuple[int, int]:
        """
        Convert geo to tile fractional coordinates for level in use.
        xgeo   geo longitude in degrees
        ygeo   geo latitude in degrees

        Note that we assume the point *is* on the map!
        """

        raise Exception('You must override BaseTiles.Geo2Tile(xgeo, ygeo)')

    def Tile2Geo(self, xtile: float, ytile: float) -> Tuple[float, float]:
        """
        Convert tile fractional coordinates to geo for level in use.

        xtile  tile fractional X coordinate
        ytile  tile fractional Y coordinate

        Note that we assume the point *is* on the map!
        """

        raise Exception('You must override BaseTiles.Tile2Geo(xtile, ytile)')
