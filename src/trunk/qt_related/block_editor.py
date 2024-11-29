from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem, QGraphicsItem
)
from PySide6.QtGui import QColor, QPainterPath, QPainter, QTransform


class BlockEditorView(QGraphicsView):
    """
    BlockEditorView
    """
    def __init__(self):
        super().__init__()
        self.scene = BlockEditorScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)


class BlockEditorScene(QGraphicsScene):
    """
    BlockEditorScene
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []
        self.temp_connection = None  # Temporary connection for creating new links

    def addItem(self, item: QGraphicsItem):
        """

        :param item:
        """
        super().addItem(item)
        item.scene2 = self

    def update_connections(self):
        """
        update_connections
        """
        for connection in self.connections:
            connection.update_path()

    def mousePressEvent(self, event):
        """

        :param event:
        """
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, ConnectionPoint):
            self.temp_connection = ConnectionItem(item, None)
            self.addItem(self.temp_connection)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """

        :param event:
        """
        if self.temp_connection:
            self.temp_connection.update_temp_path(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """

        :param event:
        """
        if self.temp_connection:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, ConnectionPoint) and item != self.temp_connection.start_point:
                self.temp_connection.end_point = item
                self.temp_connection.update_path()
                self.connections.append(self.temp_connection)
            else:
                self.removeItem(self.temp_connection)
            self.temp_connection = None
        super().mouseReleaseEvent(event)


class ConnectionPoint(QGraphicsRectItem):
    """
    ConnectionPoint
    """
    def __init__(self, parent_block, x_offset, y_offset):
        super().__init__(-5, -5, 10, 10)
        self.setParentItem(parent_block)
        self.setPos(parent_block.rect().x() + x_offset, parent_block.rect().y() + y_offset)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setBrush(QColor("blue"))  # Use QColor here


class BlockItem(QGraphicsRectItem):
    """
    BlockItem
    """
    def __init__(self, x, y, width, height, label):
        super().__init__(x, y, width, height)
        self._scene: BlockEditorScene | None = None
        self.label = QGraphicsTextItem(label, self)
        self.label.setPos(x + 10, y + 10)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.connection_points = []
        self.add_connection_points()

    @property
    def scene2(self) -> BlockEditorScene:
        return self._scene

    @scene2.setter
    def scene2(self, val: BlockEditorScene):
        self._scene = val

    def add_connection_points(self):
        """
        add_connection_points
        """
        offsets = [
            (0, self.rect().height() / 2),  # Left center
            (self.rect().width() / 2, 0),  # Top center
            (self.rect().width(), self.rect().height() / 2),  # Right center
            (self.rect().width() / 2, self.rect().height())  # Bottom center
        ]
        for x_offset, y_offset in offsets:
            self.connection_points.append(ConnectionPoint(self, x_offset, y_offset))

    def itemChange(self, change, value):
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            self._scene.update_connections()
        return super().itemChange(change, value)


class ConnectionItem(QGraphicsPathItem):
    """
    ConnectionItem
    """
    def __init__(self, start_point, end_point):
        super().__init__()
        self.start_point = start_point
        self.end_point = end_point
        self.update_path()

    def update_path(self):
        """
        update_path
        """
        if self.start_point and self.end_point:
            start = self.start_point.scenePos()
            end = self.end_point.scenePos()
            path = QPainterPath()
            path.moveTo(start)
            path.cubicTo(
                start.x() + 50, start.y(),
                end.x() - 50, end.y(),
                end.x(), end.y()
            )
            self.setPath(path)

    def update_temp_path(self, current_pos):
        """

        :param current_pos:
        """
        if self.start_point:
            start = self.start_point.scenePos()
            path = QPainterPath()
            path.moveTo(start)
            path.lineTo(current_pos)
            self.setPath(path)


class BlockEditor(QMainWindow):
    """
    BlockEditor
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Block Editor")
        self.setGeometry(100, 100, 800, 600)

        # Set up the editor view
        self.editor_view = BlockEditorView()
        self.setCentralWidget(self.editor_view)

        # Add sample blocks
        block1 = BlockItem(50, 50, 100, 50, "Block 1")
        block2 = BlockItem(300, 200, 100, 50, "Block 2")
        self.editor_view.scene.addItem(block1)
        self.editor_view.scene.addItem(block2)


if __name__ == "__main__":
    app = QApplication([])
    editor = BlockEditor()
    editor.show()
    app.exec()
