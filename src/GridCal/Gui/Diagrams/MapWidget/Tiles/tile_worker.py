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
A server Tiles object for pySlipQt tiles.

All server tile sources should inherit from this class.
For example, see osm_tiles.py.
"""
import queue
import ssl
from urllib.request import Request, urlopen
from collections.abc import Callable
from PySide6.QtCore import QThread
from PySide6.QtGui import QPixmap

# SSL magic to solve the certificates hell
# https://stackoverflow.com/questions/68275857/urllib-error-urlerror-urlopen-error-ssl-certificate-verify-failed-certifica
ssl._create_default_https_context = ssl._create_stdlib_context


def log(val: str):
    print(val)


class TileWorker(QThread):
    """Thread class that gets request from queue, loads tile, calls callback."""

    def __init__(self,
                 id_num: int,
                 server: str,
                 tile_path: str,
                 requests_cue: queue.Queue,
                 callback: Callable[[int, float, float, QPixmap, bool], None],  # level, x, y, pixmap, error
                 error_tile: QPixmap,
                 content_type: str,
                 re_request_age: float,
                 error_image: QPixmap,
                 refresh_tiles_after_days=60):
        """
        Prepare the tile worker
        Results are returned in the callback() params.
        :param id_num: a unique numer identifying the worker instance
        :param server: server URL
        :param tile_path: path to tile on server
        :param requests_cue: the request queue
        :param callback: function to call after tile available
        :param error_tile: image of error tile
        :param content_type: expected Content-Type string
        :param re_request_age: number of days in tile age before re-requesting (0 means don't update tiles)
        :param error_image: the image to return on some error
        :param refresh_tiles_after_days:
        """
        super().__init__()

        self.id_num = id_num
        self.server = server
        self.tile_path = tile_path
        self.requests_cue = requests_cue
        self.callback: Callable[[int, float, float, QPixmap, bool], None] = callback
        self.error_tile_image = error_tile
        self.content_type = content_type
        self.re_request_age = re_request_age
        self.error_image = error_image
        self.daemon = True
        self.refresh_tiles_after_days = refresh_tiles_after_days

    def run(self):
        """

        :return:
        """
        while True:
            # get zoom level and tile coordinates to retrieve
            (level, x, y) = self.requests_cue.get()

            # try to retrieve the image
            error = False
            pixmap = self.error_image
            tile_url = self.server + self.tile_path.format(Z=level, X=x, Y=y)
            try:

                # Create a Request object with the desired headers
                response = urlopen(Request(tile_url, headers={'User-Agent': 'GridCal 5'}))

                content_type = response.info().get_content_type()

                if content_type == self.content_type:
                    data = response.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                else:
                    # show error, don't cache returned error tile
                    error = True
            except Exception as e:
                error = True
                log(f"{e} exception getting tile ({level},{x},{y}) with {tile_url}")

            # call the callback function passing level, x, y and pixmap data
            # error is False if we want to cache this tile on-disk
            self.callback(level, x, y, pixmap, error)

            # finally, removes request from queue
            self.requests_cue.task_done()
