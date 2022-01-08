import sys
from PySide2.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QApplication
from PySide2.QtGui import QBrush, QPen, QPainter
from PySide2.QtCore import Qt
import math


class DeviceMarker(QGraphicsRectItem):

    def __init__(self, x, y, size, scale, parent):
        QGraphicsRectItem.__init__(self, x, y, size, size, parent=parent)
        self.d = size
        self.r = self.d / 2
        self.d1 = self.d * scale
        self.r1 = self.d1 / 2

        # draw main circle
        self.circle = QGraphicsEllipseItem(self)
        self.circle.setRect(0, 0, self.d1, self.d1)
        x = self.r - self.r1
        y = self.r - self.r1
        self.circle.setPos(x, y)
        self.circle.setBrush(QBrush(Qt.GlobalColor.green))

        # add marker
        self.marker = QGraphicsEllipseItem(self)
        self.marker.setRect(0, 0, self.r1, self.r1)
        x = 0 - self.d1 / 4
        y = 0 - self.d1 / 4
        self.marker.setPos(x, y)
        self.marker.setBrush(QBrush(Qt.GlobalColor.red))

    def set_centered_position(self, xc, yc):
        """
        set the position based on the desired object center
        :param xc: center x
        :param yc: center y
        """
        x = xc - self.r
        y = yc - self.r
        self.setPos(x, y)

    def add_cluster_marker(self):
        pass


class VoltageLevelCircle(QGraphicsEllipseItem):

    def __init__(self, xc, yc, d, parent):
        """

        :param xc: center x
        :param yc: center y
        :param d: diameter
        :param parent: parent object
        """
        QGraphicsEllipseItem.__init__(self, parent=parent)
        self.d = d
        self.r = d / 2
        self.setRect(0, 0, d, d)
        self.set_centered_position(xc, yc)
        self.setBrush(QBrush(Qt.GlobalColor.blue))

    def set_centered_position(self, xc, yc):
        """
        set the position based on the desired object center
        :param xc: center x
        :param yc: center y
        """
        x = xc - self.r
        y = yc - self.r
        self.setPos(x, y)


class Node(QGraphicsRectItem):

    def __init__(self, x, y, size, inner_scale=1.0, opacity=0.8):
        QGraphicsRectItem.__init__(self, x, y, size, size)
        self.size = size
        self.r = self.size / 2
        self.xc = self.size / 2
        self.yc = self.size / 2

        self.inner_scale = inner_scale
        self.setOpacity(opacity)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        self.circles = list()
        self.device_markers = list()

    def add_circle(self, scale):

        d = self.size * self.inner_scale * scale  # diameter
        circle = VoltageLevelCircle(xc=self.xc, yc=self.yc, d=d, parent=self)
        self.circles.append(circle)
        return circle

    def add_device_marker(self, scale=0.1, scale2=0.8):
        """

        :param scale: scale of the marker as a proportion of the node size (i.e. 0.1-> 10%)
        :param scale2: scale of the radio for the marker positioning with respect to the inner circle
        :return:
        """
        d = self.size * scale  # diameter
        dev = DeviceMarker(0, 0, d, scale=1.0, parent=self)
        self.device_markers.append(dev)
        self.arrange_device_markers(scale2)
        return dev

    def arrange_device_markers(self, scale):
        """
        Arrange the markers
        :param scale: scale of the radio for the marker positioning with respect to the inner circle
        """

        # compute the final radius for positioning the marker
        p = self.r * self.inner_scale * scale  # radius

        # angle increment, pick the max between 10 devices of the actual number of devices
        da = 6.28 / max(10, len(self.device_markers))

        # set the position of every marker
        for i, dev in enumerate(self.device_markers):
            a = i * da - (3.14 / 2)
            x = self.xc + p * math.cos(a)
            y = self.yc + p * math.sin(a)
            dev.set_centered_position(x, y)




if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Defining a scene rect of 400x200, with it's origin at 0,0.
    # If we don't set this on creation, we can set it later with .setSceneRect
    scene = QGraphicsScene(0, 0, 600, 500)


    node = Node(0, 0, 200)

    sc = 0.6
    node.add_circle(sc)
    for _ in range(6):
        node.add_device_marker(0.2, sc + 0.3)

    node.setOpacity(0.8)
    node.setPos(200, 200)

    scene.addItem(node)

    view = QGraphicsView(scene)
    view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
    view.show()

    app.exec_()
