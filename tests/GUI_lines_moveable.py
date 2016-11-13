from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys


class ParentNode(QGraphicsRectItem):

    def __init__(self, diagramScene, parent=None, h=60, w=60):
        QGraphicsItemGroup.__init__(self, parent)

        self.scene = diagramScene
        self.h = h
        self.w = w

        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(Qt.black))
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        square = QGraphicsPolygonItem()
        square.setPolygon(QPolygonF([QPointF(0, 0), QPointF(20, 0), QPointF(20, 20), QPointF(0, 20)]))

        self.setRect(0.0, 0.0, self.w, self.h)


class ChildNode(QGraphicsItemGroup):

    def __init__(self, parent):
        QGraphicsItemGroup.__init__(self, parent)

        self.parent = parent

        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)

        triangle = QGraphicsPolygonItem()
        triangle.setPolygon(QPolygonF([QPointF(0, 0), QPointF(20, 0), QPointF(10, 20)]))
        triangle.setPen(QPen(Qt.red, 2))

        self.addToGroup(triangle)
        self.setPos(180, 180)

        #  define line at first
        self.line = self.parent.scene.addLine(self.x() + 10,
                                              self.y() + 0,
                                              self.parent.x() + self.parent.w / 2,
                                              self.parent.y() + self.parent.h)

        # self.ungrabMouse.connect(self.move)

    def move(self):
        #  define line at first
        self.line.setLine(self.x() + 10,
                          self.y() + 0,
                          self.parent.x() + self.parent.w / 2,
                          self.parent.y() + self.parent.h)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    scene = QGraphicsScene()

    n1 = ParentNode(scene)
    scene.addItem(n1)

    n2 = ChildNode(n1)
    scene.addItem(n2)

    view = QGraphicsView(scene)
    view.show()
    view.resize(600, 400)

    sys.exit(app.exec_())
