from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent
import requests


class MapWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slippy Map Widget")
        self.setGeometry(100, 100, 800, 600)

        # Create a QGraphicsView to display the map
        self.graphics_view = QGraphicsView()
        self.setCentralWidget(self.graphics_view)

        # Create a QGraphicsScene
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)

        # Set initial map parameters
        self.zoom = 0
        self.center = QPointF(0, 0)
        self.tile_size = 256  # Standard tile size
        self.tile_buffer = 1  # Number of extra tiles to load in each direction
        self.drag_start_pos = None

        # Load initial map tiles
        self.load_map_tiles()

    def mousePressEvent(self, event: QMouseEvent):
        # Record the starting position of the drag
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        # Move the map when dragging
        if self.drag_start_pos is not None:
            delta = event.pos() - self.drag_start_pos
            self.center -= delta
            self.load_map_tiles()
            self.drag_start_pos = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        # Reset drag start position
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None

    def load_map_tiles(self):
        # Calculate visible area in scene coordinates
        visible_rect = self.graphics_view.mapToScene(self.graphics_view.viewport().rect()).boundingRect()

        # Calculate the range of tiles to load based on the visible area and tile size
        left_tile = int(visible_rect.left() / self.tile_size) - self.tile_buffer
        top_tile = int(visible_rect.top() / self.tile_size) - self.tile_buffer
        right_tile = int(visible_rect.right() / self.tile_size) + self.tile_buffer
        bottom_tile = int(visible_rect.bottom() / self.tile_size) + self.tile_buffer

        # Clear existing map tiles
        self.scene.clear()

        # Download and display map tiles within the visible area and tile buffer
        for x in range(left_tile, right_tile + 1):
            for y in range(top_tile, bottom_tile + 1):
                tile_url = f"https://a.basemaps.cartocdn.com/rastertiles/voyager/{self.zoom}/{x}/{y}.png"
                tile_image = self.download_tile(tile_url)
                if tile_image:
                    pixmap = QPixmap()
                    pixmap.loadFromData(tile_image)
                    item = QGraphicsPixmapItem(pixmap)
                    item.setPos(x * self.tile_size, y * self.tile_size)
                    self.scene.addItem(item)

    def download_tile(self, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.content
            else:
                print("Failed to download tile:", response.status_code)
                return None
        except Exception as e:
            print("Failed to download tile:", e)
            return None


if __name__ == "__main__":
    app = QApplication([])
    window = MapWidget()
    window.show()
    app.exec()
