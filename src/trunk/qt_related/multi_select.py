from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QPen, QBrush, QColor, QPainter
from PySide6.QtCore import Qt


class MultiSelectScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Add items with default flags to the scene
        for i in range(5):
            item = QGraphicsRectItem(i * 30, i * 30, 50, 50)
            item.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable)
            item.setPen(QPen(Qt.black))
            item.setBrush(QBrush(QColor(255, 0, 0, 127)))  # Semi-transparent red
            self.addItem(item)


class MultiSelectView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)


if __name__ == "__main__":
    app = QApplication([])

    scene = MultiSelectScene()
    view = MultiSelectView(scene)
    view.setWindowTitle("QGraphicsScene Multi-Selection with Default Flags")
    view.show()

    app.exec()
