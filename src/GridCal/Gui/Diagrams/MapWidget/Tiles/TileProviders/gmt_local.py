"""
A tile source that serves pre-generated GMT tiles from the local filesystem.
"""

import os
import pickle
from typing import Tuple
from GridCal.Gui.Diagrams.MapWidget.Tiles.base_tiles import BaseTiles


class GmtLocalTiles(BaseTiles):
    """An object to source GMT tiles for the widget."""

    TilesetName = 'GMT local tiles'
    TilesetShortName = 'GMT tiles'
    TilesetVersion = '1.0'

    def __init__(self, tiles_dir=os.path.abspath(os.path.expanduser('~/gmt_local_tiles'))):
        """Override the base class for GMT tiles.

        Basically, just fill in the BaseTiles class with GMT values from above
        and provide the Geo2Tile() and Tile2Geo() methods.
        """

        super().__init__(levels=list(range(5)),
                         tile_width=256,
                         tile_height=256,
                         tiles_dir=tiles_dir,
                         max_lru=10000)

        self.tiles_info = "tile.info"

        if not os.path.isfile(os.path.join(tiles_dir, self.tiles_info)):
            msg = f"The GMT tiles directory '{tiles_dir}' doesn't appear to be setup?"
            raise RuntimeError(msg)

        # TODO: implement map wrap-around
        #        # we *can* wrap tiles in X direction, but not Y
        #        self.wrap_x = False
        #        self.wrap_y = False

        # override the tiles.py extent here, the GMT tileset is different
        self.extent = (-65.0, 295.0, -66.66, 66.66)
        self.deg_span_x = 295.0 + 65.0
        self.deg_span_y = 66.66 + 66.66

        # get tile information into instance
        self.level = min(self.levels)
        self.num_tiles_x, self.num_tiles_y, self.ppd_x, self.ppd_y = self.GetInfo(self.level)

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
        info_file = os.path.join(self.tiles_dir, '%d' % level, self.tiles_info)
        try:
            with open(info_file, 'rb') as fd:
                info = pickle.load(fd)
        except IOError:
            info = None

        return info

    def Geo2Tile(self, longitude: float, latitude: float) -> Tuple[float, float]:
        """Convert geo to tile fractional coordinates for level in use.

        geo  a tuple of geo coordinates (xgeo, ygeo)

        Returns (xtile, ytile).

        This is an easy transformation as geo coordinates are Cartesian
        for this tileset.
        """

        # get extent information
        min_xgeo, max_xgeo, min_ygeo, max_ygeo = self.extent

        # get number of degress from top-left corner
        x = longitude - min_xgeo
        y = max_ygeo - latitude

        tiles_x = x * self.ppd_x / self.tile_size_x
        tiles_y = y * self.ppd_y / self.tile_size_y

        return tiles_x, tiles_y

    def Tile2Geo(self, xtile: float, ytile: float) -> Tuple[float, float]:
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
        xgeo = xtile * tdeg_x + min_xgeo
        ygeo = max_ygeo - ytile * tdeg_y

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
