"""Keyless OpenFreeMap vector tiles drawn with the existing Qt tile pipeline."""

import os

from PySide6.QtCore import Qt

from VeraGrid.Gui.Diagrams.MapWidget.Tiles.TileProviders.mercator import MercatorTiles
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.tiles import TileCallbackBridge, Tiles
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.vector_tile_renderer import MapStyle
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.vector_tile_worker import VectorTileWorker


class OpenFreeMapTiles(MercatorTiles):
    """Use Mercator coordinates and cached Qt-rendered PNGs from vector data."""

    __slots__ = ('style',)

    def __init__(self, tiles_dir: str, style: MapStyle,
                 start_workers: bool = True) -> None:
        """
        Configure a palette-specific PNG cache and background vector workers.

        :param tiles_dir: Root containing map caches for this installation.
        :param style: Colour, light or dark Qt palette.
        :param start_workers: False for provider prototypes and isolated tests.
        """
        self.style: MapStyle = style
        # Keep vector-rendered PNGs separate from obsolete CARTO watermark tiles.
        super().__init__(tiles_dir=tiles_dir,
                         name='OpenFreeMap ' + style.name,
                         tile_set_short_name='OpenFreeMap ' + style.name,
                         tile_servers=list(('https://tiles.openfreemap.org',)),
                         attribution='© OpenMapTiles © OpenStreetMap contributors',
                         start_workers=False)
        bridge: TileCallbackBridge | None = self.tile_callback_bridge
        if start_workers and bridge is not None:
            index: int
            for index in range(2):
                worker: VectorTileWorker = VectorTileWorker(
                    id_num=index, requests_cue=self.request_queue,
                    cache_dir=os.path.join(os.path.dirname(tiles_dir), 'openfreemap_vectors'), style=style)
                worker.tile_available.connect(bridge.tile_is_available, Qt.ConnectionType.QueuedConnection)
                self.workers.append(worker)
                worker.start()
        else:
            pass

    def copy(self) -> "OpenFreeMapTiles":
        """
        Give each diagram its own worker lifecycle and tile queue.

        :return: New source with the same palette and cache location.
        """
        source: OpenFreeMapTiles = OpenFreeMapTiles(tiles_dir=self.tiles_dir, style=self.style)
        source.set_level(self.level)
        return source


def create_map_tile_sources(cache_dir: str) -> list[Tiles]:
    """
    Build the keyless desktop provider choices without starting network workers.

    :param cache_dir: Existing map cache root.
    :return: Colour, light, dark and OpenStreetMap provider prototypes.
    """
    return list((
        OpenFreeMapTiles(os.path.join(cache_dir, 'openfreemap_colour'), MapStyle.Colour, False),
        # Separate rendered caches so existing detailed tiles cannot mask the cleaner style.
        OpenFreeMapTiles(os.path.join(cache_dir, 'openfreemap_light_clean'), MapStyle.Light, False),
        OpenFreeMapTiles(os.path.join(cache_dir, 'openfreemap_dark_clean'), MapStyle.Dark, False),
        MercatorTiles(tiles_dir=os.path.join(cache_dir, 'osm'), max_zoom=20, start_workers=False),
    ))
