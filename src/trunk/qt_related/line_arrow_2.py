import sys
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QGraphicsLineItem, QGraphicsPolygonItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPolygonF, QTransform, QPen, QCursor, QColor


class ArrowHead(QGraphicsPolygonItem):
    """
    This is the arrow object
    """

    def __init__(self,
                 parent: QGraphicsLineItem,
                 arrow_size: int,
                 position: float = 0.9,
                 under: bool = False,
                 backwards: bool = False,
                 separation: int = 5):

        QGraphicsPolygonItem.__init__(self, parent=parent)

        self.parent: QGraphicsLineItem = parent
        self.arrow_size: int = arrow_size
        self.position: float = position
        self.under: bool = under
        self.backwards: float = backwards
        self.sep = separation

        self.w = arrow_size
        self.h = arrow_size

        self.setPen(Qt.NoPen)
        self.setBrush(Qt.white)
        self.redraw()

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        # self.setPen(QPen(color, w, style))
        # self.setPen(Qt.NoPen)
        self.setBrush(color)

    def set_value(self, value: float, redraw=True):
        """
        Set the sign with a value
        :param value: any real value
        :param redraw: redraw after the sign update
        """
        self.backwards = value < 0

        if redraw:
            self.redraw()

    def redraw(self) -> None:
        """
        Redraw the arrow
        """
        line = self.parent.line()

        # the angle is added 180º if the sign is negative
        angle = line.angle()
        base_pt = line.p1() + (line.p2() - line.p1()) * self.position

        p1 = -self.arrow_size if self.backwards else self.arrow_size
        p2 = -self.arrow_size if self.under else self.arrow_size
        arrow_p1 = base_pt - QTransform().rotate(-angle).map(QPointF(p1, 0))
        arrow_p2 = base_pt - QTransform().rotate(-angle).map(QPointF(p1, p2))
        arrow_polygon = QPolygonF([base_pt, arrow_p1, arrow_p2])

        self.setPolygon(arrow_polygon)


class ArrowLineItem(QGraphicsLineItem):
    def __init__(self, start, end, parent=None, backwards=False, under=False, position=0.8, h=10, w=12, separation = 5):
        super().__init__(parent)
        self.setLine(start.x(), start.y(), end.x(), end.y())

        # # Calculate arrowhead points
        # angle = self.line().angle()
        #
        # arrow_position = self.line().p1() + (self.line().p2() - self.line().p1()) * position
        #
        # if backwards:
        #     if under:
        #         arrow_p0 = QTransform().translate(0, separation).map(arrow_position)
        #         arrow_p1 = arrow_position + QTransform().rotate(-angle).translate(0, separation).map(QPointF(w, 0))
        #         arrow_p2 = arrow_position + QTransform().rotate(-angle).translate(0, separation).map(QPointF(w, h))
        #     else:
        #         arrow_p0 = QTransform().translate(0, -separation).map(arrow_position)
        #         arrow_p1 = arrow_position + QTransform().rotate(-angle).translate(0, -separation).map(QPointF(w, 0))
        #         arrow_p2 = arrow_position + QTransform().rotate(-angle).translate(0, -separation).map(QPointF(w, -h))
        # else:
        #     if under:
        #         arrow_p0 = QTransform().translate(0, separation).map(arrow_position)
        #         arrow_p1 = arrow_position - QTransform().rotate(-angle).translate(0, -separation).map(QPointF(w, 0))
        #         arrow_p2 = arrow_position - QTransform().rotate(-angle).translate(0, -separation).map(QPointF(w, -h))
        #     else:
        #         arrow_p0 = QTransform().translate(0, -separation).map(arrow_position)
        #         arrow_p1 = arrow_position - QTransform().rotate(-angle).translate(0, separation).map(QPointF(w, 0))
        #         arrow_p2 = arrow_position - QTransform().rotate(-angle).translate(0, separation).map(QPointF(w, h))
        #
        # arrow_polygon = QPolygonF([arrow_p0, arrow_p1, arrow_p2])
        #
        # self.arrowhead = QGraphicsPolygonItem(self)
        # self.arrowhead.setBrush(Qt.white)
        # self.arrowhead.setPolygon(arrow_polygon)
        # self.arrowhead.setPen(Qt.NoPen)

        self.arrow_from_1 = ArrowHead(parent=self,
                                      arrow_size=10,
                                      position=position,
                                      under=under,
                                      backwards=backwards,
                                      separation=separation)

        self.color = Qt.white
        self.width = 3
        self.style = Qt.SolidLine
        self.setPen(QPen(self.color, self.width, self.style))
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.PointingHandCursor))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    scene = QGraphicsScene()
    view = QGraphicsView(scene)

    scene.addItem(ArrowLineItem(QPointF(50, 20), QPointF(250, 60), backwards=False, under=False, position=0.8))
    scene.addItem(ArrowLineItem(QPointF(50, 60), QPointF(250, 100), backwards=True, under=False, position=0.8))
    scene.addItem(ArrowLineItem(QPointF(50, 100), QPointF(250, 140), backwards=False, under=True, position=0.2))
    scene.addItem(ArrowLineItem(QPointF(50, 140), QPointF(250, 180), backwards=True, under=True, position=0.2))

    scene.addItem(ArrowLineItem(QPointF(50, 20), QPointF(-200, 60), backwards=False, under=False, position=0.8))
    scene.addItem(ArrowLineItem(QPointF(50, 60), QPointF(-200, 100), backwards=True, under=False, position=0.8))
    scene.addItem(ArrowLineItem(QPointF(50, 100), QPointF(-200, 140), backwards=False, under=True, position=0.2))
    scene.addItem(ArrowLineItem(QPointF(50, 140), QPointF(-200, 180), backwards=True, under=True, position=0.2))

    # scene.addItem(ArrowLineItem(QPointF(50, 50), QPointF(250, 0)))
    # scene.addItem(ArrowLineItem(QPointF(50, 70), QPointF(250, 70), backwards=True))
    # scene.addItem(ArrowLineItem(QPointF(50, 90), QPointF(250, 240), backwards=True, position=0.15))

    view.show()
    sys.exit(app.exec())
