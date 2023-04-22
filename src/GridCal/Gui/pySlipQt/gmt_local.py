"""
A tile source that serves pre-generated GMT tiles from the local filesystem.
"""

import os
import pickle
import GridCal.Gui.pySlipQt.tiles as tiles
import GridCal.Gui.pySlipQt.log as log

try:
    log = log.Log('pyslipqt.log')
except AttributeError:
    # means log already set up
    pass


###############################################################################
# Change values below here to configure the GMT local tile source.
###############################################################################

# attributes used for tileset introspection
# names must be unique amongst tile modules
TilesetName = 'GMT local tiles'
TilesetShortName = 'GMT tiles'
TilesetVersion = '1.0'

# the pool of tile servers used
TileServers = None

# the path on the server to a tile
# {} params are Z=level, X=column, Y=row, origin at map top-left
TileURLPath = None

# tile levels to be used
TileLevels = range(5)

# maximum pending requests for each tile server
# unused with local tiles
MaxServerRequests = None

# set maximum number of in-memory tiles for each level
MaxLRU = 10000

# path to the INFO file for GMT tiles
TileInfoFilename = "tile.info"

# default path to the tiles directory
TilesDir = os.path.abspath(os.path.expanduser('~/gmt_local_tiles'))

################################################################################
# Class for GMT local tiles.   Builds on tiles.BaseTiles.
################################################################################

class Tiles(tiles.BaseTiles):
    """An object to source GMT tiles for the widget."""

    # size of these tiles
    TileWidth = 256
    TileHeight = 256

    def __init__(self, tiles_dir=TilesDir):
        """Override the base class for GMT tiles.

        Basically, just fill in the BaseTiles class with GMT values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        """

        super().__init__(TileLevels,
                         Tiles.TileWidth, Tiles.TileHeight,
                         tiles_dir=tiles_dir, max_lru=MaxLRU)

        if not os.path.isfile(os.path.join(tiles_dir, TileInfoFilename)):
            msg = f"The GMT tiles directory '{tiles_dir}' doesn't appear to be setup?"
            log.critical(msg)
            raise RuntimeError(msg)
            
# TODO: implement map wrap-around
#        # we *can* wrap tiles in X direction, but not Y
#        self.wrap_x = False
#        self.wrap_y = False

        # override the tiles.py extent here, the GMT tileset is different
        self.extent = (-65.0, 295.0, -66.66, 66.66)
        self.deg_span_x = 295.0 + 65.0
        self.deg_span_y = 66.66 + 66.66

        self.levels = TileLevels

        # get tile information into instance
        self.level = min(TileLevels)
        (self.num_tiles_x, self.num_tiles_y,
                        self.ppd_x, self.ppd_y) = self.GetInfo(self.level)

    def GetInfo(self, level):
        """Get tile info for a particular level.
        Override the tiles.py method.

        level  the level to get tile info for

        Returns (num_tiles_x, num_tiles_y, ppd_x, ppd_y) or None if 'levels'
        doesn't exist.
        """

        # is required level available?
        if level not in self.levels:
            return None

        # see if we can open the tile info file.
        info_file = os.path.join(self.tiles_dir, '%d' % level, TileInfoFilename)
        try:
            with open(info_file, 'rb') as fd:
                info = pickle.load(fd)
        except IOError:
            info = None

        return info

    def Geo2Tile(self, xgeo, ygeo):
        """Convert geo to tile fractional coordinates for level in use.

        geo  a tuple of geo coordinates (xgeo, ygeo)

        Returns (xtile, ytile).

        This is an easy transformation as geo coordinates are Cartesian
        for this tileset.
        """

        # unpack the 'geo' tuple
        if xgeo is not None:

            # get extent information
            (min_xgeo, max_xgeo, min_ygeo, max_ygeo) = self.extent

            # get number of degress from top-left corner
            x = xgeo - min_xgeo
            y = max_ygeo - ygeo

            tiles_x = x * self.ppd_x / self.tile_size_x
            tiles_y = y * self.ppd_y / self.tile_size_y

            return tiles_x, tiles_y
        else:
            return None

    def Tile2Geo(self, xtile, ytile):
        """Convert tile fractional coordinates to geo for level in use.

        tile  a tuple (xtile,ytile) of tile fractional coordinates

        Note that we assume the point *is* on the map!

        This is an easy transformation as geo coordinates are Cartesian for
        this tileset.
        """

        # get extent information
        (min_xgeo, max_xgeo, min_ygeo, max_ygeo) = self.extent

        # compute tile size in degrees
        tdeg_x = self.tile_size_x / self.ppd_x
        tdeg_y = self.tile_size_y / self.ppd_y

        # calculate the geo coordinates
        xgeo = xtile*tdeg_x + min_xgeo
        ygeo = max_ygeo - ytile*tdeg_y

#        if self.wrap_x:
#            while xgeo < min_xgeo:
#                xgeo += self.deg_span_x
#            while xgeo > max_xgeo:
#                xgeo -= self.deg_span_x
#        if self.wrap_x:
#            while ygeo > max_ygeo:
#                ygeo -= self.deg_span_y
#            while ygeo < min_ygeo:
#                ygeo += self.deg_span_y

        return xgeo, ygeo

