"""
A base Tiles object for pySlipQt local tiles.

All tile sources should inherit from this base class.
For example, see gmt_local.py (local tiles) and osm_tiles.py
(internet tiles).
"""

import os
import math
from PySide2.QtGui import QPixmap
import GridCal.Gui.pySlipQt.pycacheback as pycacheback
import GridCal.Gui.pySlipQt.log as log

try:
    log = log.Log('pyslipqt.log')
except AttributeError:
    # already have a log file, ignore
    pass


# set how old disk-cache tiles can be before we re-request them from the internet
# this is the number of days old a tile is before we re-request
# if 'None', never re-request tiles after first satisfied request
RefreshTilesAfterDays = 60


################################################################################
# Define a cache for tiles.  This is an in-memory cache backed to disk.
################################################################################

class Cache(pycacheback.pyCacheBack):
    """Cache for local or internet tiles.

    Instance variables we use from pyCacheBack:
        self._tiles_dir  path to the on-disk cache directory
    """

    PicExtension = 'png'
    TilePath = '{Z}/{X}/{Y}.%s' % PicExtension


    def tile_date(self, key):
        """Return the creation date of a tile given its key."""

        tile_path = self.tile_path(key)
        return os.path.getctime(tile_path)

    def tile_path(self, key):
        """Return path to a tile file given its key."""

        (level, x, y) = key
        file_path = os.path.join(self._tiles_dir,
                                 self.TilePath.format(Z=level, X=x, Y=y))
        return file_path

    def _get_from_back(self, key):
        """Retrieve value for 'key' from backing storage.

        key  tuple (level, x, y)
             where level is the level of the tile
                   x, y  is the tile coordinates (integer)

        Raises KeyError if tile not found.
        """

        # look for item in disk cache
        file_path = self.tile_path(key)
        if not os.path.exists(file_path):
            # tile not there, raise KeyError
            raise KeyError("Item with key '%s' not found in on-disk cache"
                           % str(key)) from None

        # we have the tile file - read into memory & return
        return QPixmap(file_path)

    def _put_to_back(self, key, image):
        """Put a image into on-disk cache.

        key     a tuple: (level, x, y)
                where level  level for image
                      x      integer tile coordinate
                      y      integer tile coordinate
        image   the wx.Image to save
        """

        (level, x, y) = key
        tile_path = os.path.join(self._tiles_dir,
                                 self.TilePath.format(Z=level, X=x, Y=y))
        dir_path = os.path.dirname(tile_path)
        try:
            os.makedirs(dir_path)
        except OSError:
            # we assume it's a "directory exists' error, which we ignore
            pass

        image.save(tile_path, Cache.PicExtension)

###############################################################################
# Base class for a tile source - handles access to a source of tiles.
###############################################################################

class BaseTiles(object):
    """A base tile object to source local tiles for pySlip."""

    # maximum number of in-memory cached tiles
    MaxLRU = 1000

    def __init__(self, levels, tile_width, tile_height,
                       tiles_dir, max_lru=MaxLRU):
        """Initialise a Tiles instance.

        levels       a list of level numbers that are to be served
        tile_width   width of each tile in pixels
        tile_height  height of each tile in pixels
        tiles_dir    path to on-disk tile cache directory
        max_lru      maximum number of cached in-memory tiles
        """

        # save params
        self.levels = levels
        self.tile_size_x = tile_width
        self.tile_size_y = tile_height
        self.tiles_dir = tiles_dir
        self.max_lru = max_lru

        # set min and max tile levels and current level
        self.min_level = min(self.levels)
        self.max_level = max(self.levels)
        self.level = self.min_level

# TODO: implement map wrap-around
#        self.wrap_x = False
#        self.wrap_y = False

        # setup the tile cache
        self.cache = Cache(tiles_dir=tiles_dir, max_lru=max_lru)

        #####
        # Now finish setting up
        #####

        # tiles extent for tile data (left, right, top, bottom)
        self.extent = (-180.0, 180.0, -85.0511, 85.0511)

        # check tile cache - we expect there to already be a directory
        if not os.path.isdir(tiles_dir):
            if os.path.isfile(tiles_dir):
                msg = ("%s doesn't appear to be a tile cache directory"
                       % tiles_dir)
                log.critical(msg)
                raise Exception(msg) from None

            msg = "The tiles directory %s doesn't exist." % tiles_dir
            log.critical(msg)
            raise Exception(msg) from None

# possible recursion here?
#        self.UseLevel(min(self.levels))

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
        (self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y) = info

        return True

    def GetTile(self, x, y):
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
            raise KeyError("Can't find tile for key '%s'"
                           % str((self.level, x, y))) from None

    def GetInfo(self, level):
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

        return (self.num_tiles_x, self.num_tiles_y, None, None)

    def GetExtent(self):
        """Get geo limits of the map tiles.
        
        Returns a tuple: (min_geo_x, max_geo_x, min_geo_y, max_geo_y)
        """

        return self.extent

    def tile_on_disk(self, level, x, y):
        """Return True if tile at (level, x, y) is on-disk."""

        raise Exception('You must override BaseTiles.tile_on_disk(level, x, y))')

    def setCallback(self, callback):
        """Set the "tile available" callback function.

        Only used with internet tiles.  See "tiles_net.py".
        """

        pass
        #raise Exception('You must override BaseTiles.setCallback(callback))')

    def Geo2Tile(self, xgeo, ygeo):
        """Convert geo to tile fractional coordinates for level in use.

        xgeo   geo longitude in degrees
        ygeo   geo latitude in degrees

        Note that we assume the point *is* on the map!
        """

        raise Exception('You must override BaseTiles.Geo2Tile(xgeo, ygeo)')

    def Tile2Geo(self, xtile, ytile):
        """Convert tile fractional coordinates to geo for level in use.

        xtile  tile fractional X coordinate
        ytile  tile fractional Y coordinate

        Note that we assume the point *is* on the map!
        """

        raise Exception('You must override BaseTiles.Tile2Geo(xtile, ytile)')
