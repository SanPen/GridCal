import sys
from PySide2.QtWidgets import *
from PySide2.QtCore import *


def add_objects(scene: QGraphicsScene, n=1000):
    for i in range(n):
        item = QGraphicsEllipseItem(i * 5, 10, 60, 40)
        scene.addItem(item)


class AddObjectsThreaded(QThread):

    def __init__(self, scene: QGraphicsScene, n=1000):
        QThread.__init__(self)

        self.scene = scene
        self.n = n

    def run(self):
        """
        run the file open procedure
        """
        for i in range(self.n):
            item = QGraphicsEllipseItem(i * 5, 10, 60, 40)
            self.scene.addItem(item)


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

    # add_objects(scene=view.scene, n=100)

    thr = AddObjectsThreaded(scene=view.scene, n=100)
    thr.start()

    sys.exit(app.exec_())