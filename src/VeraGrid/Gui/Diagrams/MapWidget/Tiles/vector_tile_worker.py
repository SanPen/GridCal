"""Download OpenFreeMap vector tiles and paint them off the GUI thread."""

import gzip
import hashlib
import io
import json
import os
import queue
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from VeraGrid.Gui.Diagrams.MapWidget.Tiles.tile_worker import TileWorker
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.vector_tile_renderer import MapStyle, VectorTileRenderer


def download_map_data(url: str, limit: int) -> bytes:
    """
    Read a bounded response from OpenFreeMap with an application User-Agent.

    :param url: HTTPS resource to retrieve.
    :param limit: Maximum accepted payload size in bytes.
    :return: Response bytes, with download failures propagated to the worker.
    """
    with urlopen(Request(url, headers={'User-Agent': 'VeraGrid (https://veragrid.org)'}), timeout=3.0) as response:
        payload: bytes = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError('OpenFreeMap response exceeds the map resource size limit')
    else:
        return payload


def cache_map_data(path: Path, payload: bytes) -> None:
    """
    Replace a cached resource atomically so concurrent workers never read half a tile.

    :param path: Destination beneath the existing map cache directory.
    :param payload: Validated bytes to cache.
    """
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary_path = Path(output.name)
            output.write(payload)
        os.replace(temporary_path, path)
    except OSError as error:
        # A read-only or full cache must not prevent displaying downloaded maps.
        print(f'Could not cache OpenFreeMap data: {error}')
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                print(f'Could not remove temporary OpenFreeMap cache data: {error}')
        else:
            pass


class VectorTileWorker(TileWorker):
    """Use the existing tile queue and GUI callback with a Python/Qt renderer."""

    __slots__ = ('_cache_dir', '_renderer', '_template', '_source_max_zoom', '_revision')

    def __init__(self, id_num: int, requests_cue: queue.Queue,
                 cache_dir: str, style: MapStyle) -> None:
        """
        Prepare a renderer without making network requests on the GUI thread.

        :param id_num: Worker number within one tile source.
        :param requests_cue: Existing tile request queue.
        :param cache_dir: Shared raw vector cache for all palettes.
        :param style: Requested Qt map palette.
        """
        super().__init__(id_num=id_num, server='https://tiles.openfreemap.org',
                         tile_path='', requests_cue=requests_cue,
                         content_type='application/x-protobuf', re_request_age=0.0)
        self._cache_dir: Path = Path(cache_dir)
        self._renderer: VectorTileRenderer = VectorTileRenderer(style)
        self._template: str | None = None
        self._source_max_zoom: int = 14
        self._revision: str = ''

    def load_metadata(self) -> None:
        """
        Resolve the current dated tile URL, retaining cached metadata for offline use.

        :return: None; invalid or unavailable metadata propagates to the worker.
        """
        path: Path = self._cache_dir / 'tilejson.json'
        payload: bytes | None = None
        try:
            payload = path.read_bytes()
            fresh: bool = time.time() - path.stat().st_mtime < 86400.0
        except OSError:
            fresh = False
        if not fresh:
            try:
                payload = download_map_data('https://tiles.openfreemap.org/planet/latest', 1048576)
            except OSError:
                if payload is None:
                    raise
                else:
                    pass
        else:
            pass
        metadata: dict[str, Any] = json.loads(payload)
        templates: Any = metadata.get('tiles', None)
        maximum: Any = metadata.get('maxzoom', 14)
        if (not isinstance(templates, list) or len(templates) == 0
                or not isinstance(templates[0], str) or not isinstance(maximum, int)
                or not 0 <= maximum <= 22):
            raise ValueError('Invalid OpenFreeMap tile metadata')
        else:
            pass
        template: str = templates[0]
        if (urlsplit(template).scheme != 'https' or urlsplit(template).netloc != 'tiles.openfreemap.org'
                or not all(token in template for token in ('{z}', '{x}', '{y}'))):
            raise ValueError('Unexpected OpenFreeMap vector tile URL')
        else:
            pass
        self._template = template
        self._source_max_zoom = maximum
        # Dated upstream URLs keep raw tiles from different planet revisions separate.
        self._revision = hashlib.sha256(template.encode('utf-8')).hexdigest()[:16]
        if not fresh:
            cache_map_data(path, payload)
        else:
            pass

    def render_tile(self, level: int, x: int, y: int) -> bytes:
        """
        Fetch one source tile and rasterize the requested overzoom crop.

        :param level: Requested desktop map zoom.
        :param x: Desktop tile column.
        :param y: Desktop tile row.
        :return: PNG bytes for the existing GUI tile cache.
        """
        if self._template is None:
            self.load_metadata()
        else:
            pass
        source_level: int = min(level, self._source_max_zoom)
        factor: int = 2 ** (level - source_level)
        source_x: int = x // factor
        source_y: int = y // factor
        path: Path = self._cache_dir / self._revision / str(source_level) / str(source_x) / f'{source_y}.pbf'
        payload: bytes
        cached: bool
        try:
            payload = path.read_bytes()
            cached = True
        except OSError:
            if self._template is not None:
                payload = download_map_data(self._template.format(z=source_level, x=source_x, y=source_y), 16777216)
                cached = False
            else:
                raise ValueError('OpenFreeMap tile metadata is unavailable')
        # Some endpoints serve gzip-compressed protobufs; bound decompression too.
        decoded_payload: bytes = payload
        if payload[:2] == b'\x1f\x8b':
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
                decoded_payload = compressed.read(16777217)
        else:
            pass
        if len(decoded_payload) > 16777216:
            raise ValueError('OpenFreeMap vector tile exceeds the decode size limit')
        else:
            pass
        image: bytes = self._renderer.render(decoded_payload, level, source_level, x, y)
        if not cached:
            # Cache only data that was decoded and rendered successfully.
            cache_map_data(path, payload)
        else:
            pass
        return image

    def run(self) -> None:
        """
        Convert queued vector requests into PNG results until shutdown is requested.

        :return: None.
        """
        while self._running:
            tile: tuple[int, float, float] | None = self.requests_cue.get()
            if tile is None:
                self.requests_cue.task_done()
                break
            else:
                pass
            level: int = tile[0]
            x: float = tile[1]
            y: float = tile[2]
            image: bytes = bytes()
            error: bool = False
            try:
                image = self.render_tile(level, int(x), int(y))
            except Exception as exception:
                # Match raster workers: failed tiles are reported and never cached as PNGs.
                error = True
                print(f'OpenFreeMap tile ({level}, {x}, {y}) failed: {exception}')
            self.tile_available.emit(level, x, y, image, error)
            self.requests_cue.task_done()
