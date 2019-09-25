import sys
from PySide2.QtWidgets import *
from PySide2.QtCore import *


def add_objects(scene: QGraphicsScene, n=1000):
    for i in range(n):
        item = QGraphicsEllipseItem(i * 5, 10, 60, 40)
        scene.addItem(item)


class MyView(QGraphicsView):
    def __init__(self):
        QGraphicsView.__init__(self)

        self.setGeometry(QRect(100, 100, 600, 250))

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF())

        self.setScene(self.scene)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = MyView()
    view.show()
    add_objects(scene=view.scene, n=100)
    sys.exit(app.exec_())
