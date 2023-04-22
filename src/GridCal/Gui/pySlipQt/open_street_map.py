"""
A tile source that serves OpenStreetMap tiles from server(s).
"""

import math
import GridCal.Gui.pySlipQt.tiles_net as tiles_net


###############################################################################
# Change values below here to configure this tile source.
###############################################################################

# attributes used for tileset introspection
# names must be unique amongst tile modules
TilesetName = 'OpenStreetMap Tiles'
TilesetShortName = 'OSM Tiles'
TilesetVersion = '1.0'

# the pool of tile servers used
TileServers = [
               # 'https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all',
               'https://tile.openstreetmap.org',
               # 'https://a.tile.openstreetmap.org',
               # 'https://b.tile.openstreetmap.org',
               # 'https://c.tile.openstreetmap.org',
              ]

# the path on the server to a tile
# {} params are Z=level, X=column, Y=row, origin at map top-left
TileURLPath = '/{Z}/{X}/{Y}.png'

# tile levels to be used
TileLevels = range(17)

# maximum pending requests for each tile server
MaxServerRequests = 2

# set maximum number of in-memory tiles for each level
MaxLRU = 10000

# where earlier-cached tiles will be
# this can be overridden in the __init__ method
TilesDir = 'open_street_map_tiles'


################################################################################
# Class for these tiles.   Builds on tiles_net.Tiles.
################################################################################

class Tiles(tiles_net.Tiles):
    """An object to source server tiles for pySlipQt."""

    # size of tiles
    TileWidth = 256
    TileHeight = 256

    def __init__(self, tiles_dir=TilesDir, http_proxy=None):
        """Override the base class for these tiles.

        Basically, just fill in the BaseTiles class with values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        """

        super().__init__(TileLevels,
                         Tiles.TileWidth, Tiles.TileHeight,
                         tiles_dir=tiles_dir,
                         servers=TileServers, url_path=TileURLPath,
                         max_server_requests=MaxServerRequests,
                         max_lru=MaxLRU, http_proxy=http_proxy)
# TODO: implement map wrap-around
#        self.wrap_x = True
#        self.wrap_y = False

        # get tile information into instance
        self.level = min(TileLevels)
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = self.GetInfo(self.level)

    def Geo2Tile(self, xgeo, ygeo):
        """
        Convert geo to tile fractional coordinates for level in use.
        geo  tuple of geo coordinates (xgeo, ygeo)
        Note that we assume the point *is* on the map!
        Code taken from [http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames]
        """
        lat_rad = math.radians(ygeo)
        n = 2.0 ** self.level
        xtile = (xgeo + 180.0) / 360.0 * n
        ytile = ((1.0 - math.log(math.tan(lat_rad) + (1.0/math.cos(lat_rad))) / math.pi) / 2.0) * n

        return xtile, ytile

    def Tile2Geo(self, xtile, ytile):
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
