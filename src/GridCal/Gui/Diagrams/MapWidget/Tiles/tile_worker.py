"""
A server Tiles object for pySlipQt tiles.

All server tile sources should inherit from this class.
For example, see osm_tiles.py.
"""
import queue
import ssl
from urllib import request
from collections.abc import Callable
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QThread
from GridCal.Gui.Diagrams.MapWidget.logger import log


# SSL magic to solve the certificates hell
# https://stackoverflow.com/questions/68275857/urllib-error-urlerror-urlopen-error-ssl-certificate-verify-failed-certifica
ssl._create_default_https_context = ssl._create_stdlib_context


class TileWorker(QThread):
    """Thread class that gets request from queue, loads tile, calls callback."""

    def __init__(self,
                 id_num: int,
                 server: str,
                 tilepath: str,
                 requests: queue.Queue,
                 callback: Callable[[int, float, float, QPixmap, bool], None],  # level, x, y, pixmap, error
                 error_tile: QPixmap,
                 content_type: str,
                 rerequest_age: float,
                 error_image: QPixmap,
                 refresh_tiles_after_days=60):
        """
        Prepare the tile worker
        Results are returned in the callback() params.
        :param id_num: a unique numer identifying the worker instance
        :param server: server URL
        :param tilepath: path to tile on server
        :param requests: the request queue
        :param callback: function to call after tile available
        :param error_tile: image of error tile
        :param content_type: expected Content-Type string
        :param rerequest_age: number of days in tile age before re-requesting (0 means don't update tiles)
        :param error_image: the image to return on some error
        :param refresh_tiles_after_days:
        """

        QThread.__init__(self)

        self.id_num = id_num
        self.server = server
        self.tilepath = tilepath
        self.requests = requests
        self.callback: Callable[[int, float, float, QPixmap, bool], None] = callback
        self.error_tile_image = error_tile
        self.content_type = content_type
        self.rerequest_age = rerequest_age
        self.error_image = error_image
        self.daemon = True
        self.refresh_tiles_after_days = refresh_tiles_after_days

    def run(self):
        """

        :return:
        """
        while True:
            # get zoom level and tile coordinates to retrieve
            (level, x, y) = self.requests.get()

            # try to retrieve the image
            error = False
            pixmap = self.error_image
            try:
                tile_url = self.server + self.tilepath.format(Z=level, X=x, Y=y)
                response = request.urlopen(tile_url)
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
                log('%s exception getting tile (%d,%d,%d)' % (type(e).__name__, level, x, y))

            # call the callback function passing level, x, y and pixmap data
            # error is False if we want to cache this tile on-disk
            self.callback(level, x, y, pixmap, error)

            # finally, removes request from queue
            self.requests.task_done()
