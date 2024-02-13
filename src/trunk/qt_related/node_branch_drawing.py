from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *


class Path(QGraphicsPathItem):

    def __init__(self, path, scene):
        """

        :param path:
        :param scene:
        """
        QGraphicsPathItem.__init__(self, path)

        self.path_ = path

        for i in range(self.path_.elementCount()):
            node = Node(self, i)
            node.setPos(QPointF(self.path_.elementAt(i)))
            scene.addItem(node)

        self.setPen(QPen(Qt.red, 1.75))

    def update_element(self, index, pos):
        """

        :param index:
        :param pos:
        :return:
        """
        self.path_.setElementPositionAt(index, pos.x(), pos.y())
        self.setPath(self.path_)


class Node(QGraphicsEllipseItem):

    def __init__(self, path: Path, index, rad=5):
        """

        :param path:
        :param index:
        :param rad:
        """
        QGraphicsEllipseItem.__init__(self, -rad, -rad, 2*rad, 2*rad)

        self.rad = rad
        self.path = path
        self.index = index

        self.setZValue(1)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setBrush(Qt.green)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.path.update_element(self.index, value.toPoint())
        return QGraphicsEllipseItem.itemChange(self, change, value)


if __name__ == "__main__":

    """
    https://stackoverflow.com/questions/2173146/how-can-i-draw-nodes-and-edges-in-pyqt
    

    QGrahpicsItem, QPainterPath and QPainterPath. Element are the classes you are looking for. 
    Specifically, QPainterPath implements the kind of vector functionality you expect in 
    applications such as CorelDraw, Adobe Illustrator, or Inkscape.
    
    The example below benefits from the pre-existing QGraphicsEllipseItem (for rendering nodes) 
    and QGraphicsPathItem (for rendering the path itself), which inherit from QGraphicsItem.
    
    The Path constructor iterates over the QPainterPath elements, creating Node items for each one; 
    Each of them, in turn, send updates to the parent Path object, which updates its path property accordingly.
    
    I found much, much easier to study the C++ Qt4 Docs than the rather less structured PyQt docs found elsewhere. 
    Once you get used to mentally translate between C++ and Python, the docs themselves are a powerful way 
    to learn how to use each class.

    
    """

    app = QApplication([])

    path_ = QPainterPath()
    path_.moveTo(0, 0)
    path_.cubicTo(-30, 70, 35, 115, 100, 100)
    path_.lineTo(200, 100)
    path_.cubicTo(200, 30, 150, -35, 60, -30)

    scene_ = QGraphicsScene()
    scene_.addItem(Path(path_, scene_))

    view_ = QGraphicsView(scene_)
    view_.setRenderHint(QPainter.Antialiasing)
    view_.resize(600, 400)
    view_.show()
    app.exec_()
