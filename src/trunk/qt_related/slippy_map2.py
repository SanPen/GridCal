import sys
import os
import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QImage, QPainter, QPixmap, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QMainWindow

import requests

TILE_SIZE = 256
CACHE_DIR = "tile_cache"
CARTODB_POSITRON_URL = "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"


def get_tile_url(z, x, y):
    return CARTODB_POSITRON_URL.format(z=z, x=x, y=y)


def get_cache_path(z, x, y):
    return os.path.join(CACHE_DIR, f"{z}_{x}_{y}.png")


def download_tile(z, x, y):
    url = get_tile_url(z, x, y)
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    return None


def get_tile(z, x, y):
    cache_path = get_cache_path(z, x, y)

    # Check if the tile is already in the cache
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    # Download the tile if it's not in the cache
    tile_data = download_tile(z, x, y)
    if tile_data:
        # Save the downloaded tile to the cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(tile_data)
        return tile_data

    return None


class TileItem(QGraphicsPixmapItem):
    def __init__(self, z, x, y):
        super().__init__()
        self.z = z
        self.x = x
        self.y = y
        self.setPixmap(self.get_tile_pixmap())

    def get_tile_pixmap(self):
        tile_data = get_tile(self.z, self.x, self.y)
        if tile_data:
            image = QImage.fromData(tile_data)
            pixmap = QPixmap.fromImage(image)
            return pixmap
        else:
            return QPixmap(TILE_SIZE, TILE_SIZE)  # return an empty pixmap if the tile fails to load


class MapView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.zoom = 2
        self.visible_tiles = set()
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.draw_tiles()

    def draw_tiles(self):
        current_visible_tiles = self.get_visible_tiles()

        # Add new tiles
        for tile in current_visible_tiles:
            if tile not in self.visible_tiles:
                z, x, y = tile
                tile_item = TileItem(z, x, y)
                tile_item.setPos(x * TILE_SIZE, y * TILE_SIZE)
                self.scene.addItem(tile_item)
                self.visible_tiles.add(tile)

        # Remove old tiles
        for tile in list(self.visible_tiles):
            if tile not in current_visible_tiles:
                self.visible_tiles.remove(tile)
                for item in self.scene.items():
                    if isinstance(item, TileItem) and (item.z, item.x, item.y) == tile:
                        self.scene.removeItem(item)

        # Set scene rect to the size of the view
        self.setSceneRect(QRectF(0, 0, self.viewport().width(), self.viewport().height()))

    def get_visible_tiles(self):
        visible_tiles = set()
        rect = self.mapToScene(self.viewport().rect()).boundingRect()
        top_left = rect.topLeft()
        bottom_right = rect.bottomRight()

        # Determine the range of tiles to fetch
        start_x = int(math.floor(top_left.x() / TILE_SIZE))
        start_y = int(math.floor(top_left.y() / TILE_SIZE))
        end_x = int(math.ceil(bottom_right.x() / TILE_SIZE))
        end_y = int(math.ceil(bottom_right.y() / TILE_SIZE))

        num_tiles = 2 ** self.zoom
        for x in range(start_x, end_x):
            if x < 0 or x >= num_tiles:
                continue
            for y in range(start_y, end_y):
                if y < 0 or y >= num_tiles:
                    continue
                visible_tiles.add((self.zoom, x, y))

        return visible_tiles

    def wheelEvent(self, event: QWheelEvent):
        old_center = self.mapToScene(self.viewport().rect().center())

        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)
        self.zoom += 1 if event.angleDelta().y() > 0 else -1

        new_center = self.mapToScene(self.viewport().rect().center())
        delta = new_center - old_center

        self.translate(delta.x(), delta.y())
        self.draw_tiles()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.draw_tiles()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self.draw_tiles()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slippy Map")
        self.setGeometry(100, 100, 800, 600)
        self.map_view = MapView()
        self.setCentralWidget(self.map_view)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
