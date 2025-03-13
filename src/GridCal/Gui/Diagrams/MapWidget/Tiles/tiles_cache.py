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
A base Tiles object for pySlipQt local tiles.

All tile sources should inherit from this base class.
For example, see gmt_local.py (local tiles) and osm_tiles.py
(internet tiles).
"""

import os
from typing import Tuple
from PySide6.QtGui import QPixmap
import GridCal.Gui.Diagrams.MapWidget.Tiles.pycacheback as pycacheback


class TilesCache(pycacheback.PyCacheBack):
    """Cache for local or internet tiles.

    Instance variables we use from pyCacheBack:
        self._tiles_dir  path to the on-disk cache directory
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.PicExtension = 'png'
        self.TilePath = '{Z}/{X}/{Y}.%s' % self.PicExtension

    def tile_date(self, key: Tuple[int, float, float]):
        """Return the creation date of a tile given its key."""

        tile_path = self.tile_path(key)
        return os.path.getctime(tile_path)

    def tile_path(self, key: Tuple[int, float, float]) -> str:
        """Return path to a tile file given its key."""

        (level, x, y) = key
        file_path = os.path.join(self._tiles_dir, self.TilePath.format(Z=level, X=x, Y=y))
        return file_path

    def _get_from_back(self, key: Tuple[int, float, float]) -> QPixmap:
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

    def _put_to_back(self, key: Tuple[int, float, float], image: QPixmap):
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
            # we assume it's a 'directory exists' error, which we ignore
            pass

        image.save(tile_path, self.PicExtension)

    def add(self, key: Tuple[int, float, float], image: QPixmap):
        """
        Add entry
        :param key: key
        :param image: value
        """
        self._put_to_back(key, image)
