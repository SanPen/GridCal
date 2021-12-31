import sys
from PySide2.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QApplication
from PySide2.QtGui import QBrush, QPen
from PySide2.QtCore import Qt
import math


class DeviceMarker(QGraphicsRectItem):

    def __init__(self, x, y, w, h, scale=0.8, parent=None):
        QGraphicsRectItem.__init__(self, x, y, w, h, parent=parent)
        self.h = h
        self.w = w
        self.circles = list()

        # draw main circle
        d = min(self.h, self.w) * scale  # diameter
        self.circle = QGraphicsEllipseItem(self)
        self.circle.setRect(0, 0, d, d)
        x = self.w / 2 - d / 2
        y = self.h / 2 - d / 2
        self.circle.setPos(x, y)
        self.circle.setBrush(QBrush(Qt.GlobalColor.green))

        # add marker
        self.marker = QGraphicsEllipseItem(self)
        self.marker.setRect(0, 0, d/2, d/2)
        x = 0 - d / 4
        y = 0 - d / 4
        self.marker.setPos(x, y)
        self.marker.setBrush(QBrush(Qt.GlobalColor.red))

    def set_centered_position(self, xc, yc):
        d = min(self.h, self.w)
        x = xc - d / 2
        y = yc - d / 2
        self.setPos(x, y)

    def add_cluster_marker(self):
        pass


class Node(QGraphicsRectItem):

    def __init__(self, x, y, w, h, inner_scale=1.0):
        QGraphicsRectItem.__init__(self, x, y, w, h)
        self.h = h
        self.w = w

        self.inner_scale = inner_scale

        self.circles = list()
        self.device_markers = list()

    def add_circle(self, scale):

        d = min(self.h, self.w) * self.inner_scale * scale  # diameter
        circle = QGraphicsEllipseItem(self)
        circle.setRect(0, 0, d, d)
        x = self.w / 2 - d / 2
        y = self.h / 2 - d / 2
        circle.setPos(x, y)

        circle.setBrush(QBrush(Qt.GlobalColor.blue))

        self.circles.append(circle)

    def add_device_marker(self, scale=0.1, scale2=0.8):

        d = min(self.h, self.w) * scale  # diameter
        dev = DeviceMarker(0, 0, d, d, scale=1.0, parent=self)
        self.device_markers.append(dev)
        self.arrange_device_markers(scale2)

    def arrange_device_markers(self, scale):
        d = min(self.h, self.w)
        p = d / 2 * self.inner_scale * scale
        # da = 6.28 / len(self.device_markers)
        da = 6.28 / 10
        xc = self.w / 2
        yc = self.h / 2
        for i, dev in enumerate(self.device_markers):
            a = i * da - (3.14 / 2)
            x = xc + p * math.cos(a)
            y = yc + p * math.sin(a)
            dev.set_centered_position(x, y)




if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Defining a scene rect of 400x200, with it's origin at 0,0.
    # If we don't set this on creation, we can set it later with .setSceneRect
    scene = QGraphicsScene(0, 0, 600, 500)


    node = Node(0, 0, 100, 100)

    sc = 0.8
    node.add_circle(sc)
    for i in range(8):
        node.add_device_marker(0.2, sc + 0.3)


    scene.addItem(node)

    node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)

    view = QGraphicsView(scene)
    view.show()
    app.exec_()
