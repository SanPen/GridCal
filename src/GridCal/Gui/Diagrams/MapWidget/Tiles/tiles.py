"""
A server Tiles object for pySlipQt tiles.

All server tile sources should inherit from this class.
For example, see osm_tiles.py.
"""

import os
import time
import math
import traceback
import urllib
from urllib import request
from urllib.error import HTTPError
import queue
from PySide6.QtGui import QPixmap, QColor
from typing import List, Union
from collections.abc import Callable
from GridCal.Gui.Diagrams.MapWidget.Tiles.base_tiles import BaseTiles
from GridCal.Gui.Diagrams.MapWidget.Tiles.tile_worker import TileWorker
from GridCal.Gui.Diagrams.MapWidget.logger import log

# # set how old disk-cache tiles can be before we re-request them from the
# # server.  this is the number of days old a tile is before we re-request.
# # if 'None', never re-request tiles after first satisfied request.
# RefreshTilesAfterDays = 60

# define the error messages for various failures
StatusError = {401: 'Looks like you need to be authorised for this server.',
               404: 'You might need to check the tile addressing for this server.',
               429: 'You are asking for too many tiles.', }


class Tiles(BaseTiles):
    """
    A tile object to source server tiles for the widget.
    """

    # allowed file types and associated values
    AllowedFileTypes = {'png': 'PNG', 'jpg': 'JPG'}

    # the number of seconds in a day
    SecondsInADay = 60 * 60 * 24

    def __init__(self,
                 TilesetName: str,
                 TilesetShortName: str,
                 TilesetVersion: str,
                 levels: List[int],
                 tile_width: int,
                 tile_height: int,
                 tiles_dir: str,
                 max_lru: int,
                 servers: List[str],
                 url_path: str,
                 max_server_requests: int,
                 http_proxy,
                 refetch_days: int = 60):
        """
        Initialise a Tiles instance.
        :param levels: a list of level numbers that are to be served
        :param tile_width: width of each tile in pixels
        :param tile_height: height of each tile in pixels
        :param tiles_dir: path to on-disk tile cache directory
        :param max_lru: maximum number of tiles cached in-memory
        :param servers: list of tile servers
        :param url_path: path on server to each tile
        :param max_server_requests: maximum number of requests per server
        :param http_proxy: proxy to use if required
        :param refetch_days: fetch new server tile if older than this in days (0 means don't ever update tiles)
        """
        self.TilesetName = TilesetName
        self.TilesetShortName = TilesetShortName
        self.TilesetVersion = TilesetVersion

        # prepare the tile cache directory, if required
        # we have to do this *before* the base class initialization!
        for level in levels:
            level_dir = os.path.join(tiles_dir, '%d' % level)
            if not os.path.isdir(level_dir):
                os.makedirs(level_dir)

        # perform the base class initialization
        super().__init__(levels, tile_width, tile_height, tiles_dir, max_lru)

        # save params not saved in super()
        self.servers = servers
        self.url_path = url_path
        self.max_requests = max_server_requests
        self.http_proxy = http_proxy
        self.refresh_tiles_after_days = refetch_days

        # callback must be set by higher-level copde
        self.callback: Union[None, Callable[[int, float, float, QPixmap, bool], None]] = None

        # calculate a re-request age, if specified
        self.rerequest_age = (time.time() - self.refresh_tiles_after_days * self.SecondsInADay)

        # tiles extent for tile data (left, right, top, bottom)
        self.extent = (-180.0, 180.0, -85.0511, 85.0511)

        self.level = levels[len(levels) - 1]
        self.num_tiles_x = 0
        self.num_tiles_y = 0
        self.ppd_x = 0
        self.ppd_y = 0

        # figure out tile filename extension from 'url_path'
        tile_extension = os.path.splitext(url_path)[1][1:]
        tile_extension_lower = tile_extension.lower()  # ensure lower case

        # determine the file bitmap type
        try:
            self.filetype = self.AllowedFileTypes[tile_extension_lower]
        except KeyError as e:
            raise TypeError("Bad tile_extension value, got '%s', "
                            "expected one of %s"
                            % (str(tile_extension),
                               str(self.AllowedFileTypes.keys()))) from None

        # compose the expected 'Content-Type' string on request result
        # if we get here we know the extension is in self.AllowedFileTypes
        if tile_extension_lower == 'jpg':
            self.content_type = 'image/jpeg'
        elif tile_extension_lower == 'png':
            self.content_type = 'image/png'

        # set the list of queued unsatisfied requests to 'empty'
        self.queued_requests = {}

        # prepare the "pending" and "error" images
        self.pending_tile = QPixmap(256, 256)
        self.pending_tile.fill(QColor.fromRgb(50, 50, 50, 255))
        # self.pending_tile.loadFromData(std.getPendingImage())

        self.error_tile = QPixmap(256, 256)
        self.error_tile.fill(QColor.fromRgb(255, 0, 0, 255))
        # self.error_tile.loadFromData(std.getErrorImage())

        # test for firewall - use proxy (if supplied)
        test_url = self.servers[0] + self.url_path.format(Z=0, X=0, Y=0)
        try:
            # r = request.Request(test_url, headers={'User-Agent': 'Nokia (PyQt) Graphics Dojo 1.0'})
            # response = request.urlopen(r).read()
            request.urlopen(test_url)
        except HTTPError as e:
            # if it's fatal, log it and die, otherwise try a proxy
            status_code = e.code
            log('Error: test_url=%s, status_code=%s' % (test_url, str(status_code)))
            error_msg = StatusError.get(status_code, None)
            if status_code:
                msg = "\nYou got a " + str(status_code) + " (" + str(error_msg) + ") error from: " + str(test_url)
                print(msg)
                # raise RuntimeError(msg) from None

            log('%s exception doing simple connection to: %s' % (type(e).__name__, test_url))
            log(''.join(traceback.format_exc()))

            if http_proxy:
                proxy = request.ProxyHandler({'http': http_proxy})
                opener = request.build_opener(proxy)
                request.install_opener(opener)
                try:
                    request.urlopen(test_url)
                except:
                    msg = "Using HTTP proxy but still can't get through a firewall!"
                    print(msg)
                    # raise Exception(msg) from None
            else:
                msg = "There is a firewall but you didn't give me an HTTP proxy to get through it?"
                print(msg)
                # raise Exception(msg) from None
        except urllib.error.URLError as e:
            print(e)

        # set up the request queue and worker threads
        self.request_queue = queue.Queue()  # entries are (level, x, y)
        self.workers = []
        for server in self.servers:
            for num_thread in range(self.max_requests):
                worker = TileWorker(id_num=num_thread,
                                    server=server,
                                    tilepath=self.url_path,
                                    requests=self.request_queue,
                                    callback=self.tile_is_available,
                                    error_tile=self.error_tile,
                                    content_type=self.content_type,
                                    rerequest_age=self.rerequest_age,
                                    error_image=self.error_tile,
                                    refresh_tiles_after_days=60)
                self.workers.append(worker)
                worker.start()

    def UseLevel(self, level):
        """
        Prepare to serve tiles from the required level.

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

        # flush any outstanding requests.
        # we do this to speed up multiple-level zooms so the user doesn't
        # sit waiting for tiles to arrive that won't be shown.
        self.FlushRequests()

        return True

    def GetTile(self, x, y) -> QPixmap:
        """
        Get bitmap for tile at tile coords (x, y) and current level.

        x  X coord of tile required (tile coordinates)
        y  Y coord of tile required (tile coordinates)

        Returns bitmap object for the tile image.
        Tile coordinates are measured from map top-left.

        We override the existing GetTile() method to add code to retrieve
        tiles from the servers if not in on-disk cache.

        We also check the date on the tile from disk-cache.  If "too old",
        return old tile after starting the process to get new tile from servers.
        """

        try:
            # get tile from cache
            tile = self.cache[(self.level, x, y)]
            if self.tile_on_disk(self.level, x, y):
                tile_date = self.cache.tile_date((self.level, x, y))
                if self.rerequest_age and (tile_date < self.rerequest_age):
                    self.get_server_tile(self.level, x, y)
        except KeyError as e:
            # not cached, start process of getting tile from 'net, return 'pending' image
            self.get_server_tile(self.level, x, y)
            tile = self.pending_tile

        return tile

    def GetInfo(self, level):
        """
        Get tile info for a particular level.

        level  the level to get tile info for

        Returns (num_tiles_x, num_tiles_y, ppd_x, ppd_y) or None if 'level'
        doesn't exist.

        Note that ppd_? may be meaningless for some tiles, so its
        value will be None.

        This method is for server tiles.  It will be overridden for GMT tiles.
        """

        # is required level available?
        if level not in self.levels:
            return None

        # otherwise get the information
        self.num_tiles_x = int(math.pow(2, level))
        self.num_tiles_y = int(math.pow(2, level))

        return self.num_tiles_x, self.num_tiles_y, None, None

    def FlushRequests(self):
        """
        Delete any outstanding tile requests.
        """

        # if we are serving server tiles ...
        if self.servers:
            with self.request_queue.mutex:
                self.request_queue.queue.clear()
            self.queued_requests.clear()

    def get_server_tile(self, level: int, x: float, y: float) -> None:
        """
        Start the process to get a server tile.

        level, x, y  identify the required tile

        If we don't already have this tile (or getting it), queue a request and
        also put the request into a 'queued request' dictionary.  We
        do this since we can't peek into a queue to see what's there.
        """

        tile_key = (level, x, y)
        if tile_key not in self.queued_requests:
            # add tile request to the server request queue
            self.request_queue.put(tile_key)
            self.queued_requests[tile_key] = True

    def tile_on_disk(self, level: int, x: float, y: float):
        """Return True if tile at (level, x, y) is on-disk."""

        tile_path = self.cache.tile_path((level, x, y))
        return os.path.exists(tile_path)

    def setCallback(self, callback: Callable[[int, float, float, QPixmap, bool], None]):
        """Set the "tile available" callback.

        callback  reference to object to call when tile is found.
        """

        self.callback = callback

    def tile_is_available(self, level: int, x: float, y: float, image: QPixmap, error: bool):
        """
        Callback routine - a 'net tile is available.

        level   level for the tile
        x       x coordinate of tile
        y       y coordinate of tile
        image   tile image data
        error   True if image is 'error' image, don't cache in that case
        """

        # put image into in-memory cache, but error images don't go to disk
        self.cache[(level, x, y)] = image
        if not error:
            self.cache.add(key=(level, x, y), image=image)

        # remove the request from the queued requests
        # note that it may not be there - a level change can flush the dict
        try:
            del self.queued_requests[(level, x, y)]
        except KeyError:
            pass

        # tell the world a new tile is available
        if self.callback:
            self.callback(level, x, y, image, True)
        else:
            msg = f'tile_is_available: self.callback is NOT SET!'
            raise RuntimeError(msg) from None

    def SetAgeThresholdDays(self, num_days):
        """
        Set the tile refetch threshold time.

        num_days  number of days before refetching tiles

        If 'num_days' is 0 refetching is inhibited.
        """

        # update the global in case we instantiate again

        self.refresh_tiles_after_days = num_days

        # recalculate this instance's age threshold in UNIX time
        self.rerequest_age = time.time() - self.refresh_tiles_after_days * self.SecondsInADay
