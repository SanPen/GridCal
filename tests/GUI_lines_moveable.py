from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys

class LineUpdateMixin(object):
    def __init__(self, parent):
        super(LineUpdateMixin, self).__init__(parent)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_line(value)
        return super(LineUpdateMixin, self).itemChange(change, value)


class Triangle(LineUpdateMixin, QGraphicsPolygonItem):
    pass


class ParentNode(QGraphicsRectItem):
    def __init__(self, diagramScene, parent=None, h=60, w=60):
        super(ParentNode, self).__init__(parent)
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(Qt.black))
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        square = QGraphicsPolygonItem()
        square.setPolygon(QPolygonF([QPointF(0, 0), QPointF(20, 0), QPointF(20, 20), QPointF(0, 20)]))

        self.setRect(0.0, 0.0, w, h)


class ChildNode(QGraphicsItemGroup):
    def __init__(self, parent):
        super(ChildNode, self).__init__(parent)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)

        self.line = QGraphicsLineItem()
        parent.scene().addItem(self.line)
        self.update_line(self.pos())

        triangle = Triangle(self)
        triangle.setPolygon(QPolygonF([QPointF(0, 0), QPointF(20, 0), QPointF(10, 20)]))
        triangle.setPen(QPen(Qt.red, 2))

        ln = QGraphicsLineItem(self)
        ln.setLine(10, 0, 10, -10)
        self.addToGroup(ln)

        self.addToGroup(triangle)
        self.setPos(180, 180)

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.line.setLine(
            pos.x() + 10, pos.y() - 10,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
            )

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
