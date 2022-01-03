import math, sys
from PySide2 import QtWidgets, QtCore, QtGui


'''
See
https://stackoverflow.com/questions/44246283/how-to-add-a-arrow-head-to-my-line-in-pyqt4
'''


class Path(QtWidgets.QGraphicsPathItem):

    def __init__(self, source: QtCore.QPointF = None, destination: QtCore.QPointF = None, *args, **kwargs):
        super(Path, self).__init__(*args, **kwargs)

        self._sourcePoint = source
        self._destinationPoint = destination

        self._arrow_height = 5
        self._arrow_width = 4

    def setSource(self, point: QtCore.QPointF):
        self._sourcePoint = point

    def setDestination(self, point: QtCore.QPointF):
        self._destinationPoint = point

    def directPath(self):
        path = QtGui.QPainterPath(self._sourcePoint)
        path.lineTo(self._destinationPoint)
        return path

    def squarePath(self):
        s = self._sourcePoint
        d = self._destinationPoint

        mid_x = s.x() + ((d.x() - s.x()) * 0.5)

        path = QtGui.QPainterPath(QtCore.QPointF(s.x(), s.y()))
        path.lineTo(mid_x, s.y())
        path.lineTo(mid_x, d.y())
        path.lineTo(d.x(), d.y())

        return path

    def bezierPath(self):
        s = self._sourcePoint
        d = self._destinationPoint

        source_x, source_y = s.x(), s.y()
        destination_x, destination_y = d.x(), d.y()

        dist = (d.x() - s.x()) * 0.5

        cpx_s = +dist
        cpx_d = -dist
        cpy_s = 0
        cpy_d = 0

        if (s.x() > d.x()) or (s.x() < d.x()):
            cpx_d *= -1
            cpx_s *= -1

            cpy_d = ((source_y - destination_y) / math.fabs((source_y - destination_y) if (source_y - destination_y) != 0 else 0.00001)) * 150

            cpy_s = ((destination_y - source_y) / math.fabs((destination_y - source_y) if (destination_y - source_y) != 0 else 0.00001)) * 150

        path = QtGui.QPainterPath(self._sourcePoint)

        path.cubicTo(destination_x + cpx_d, destination_y + cpy_d, source_x + cpx_s, source_y + cpy_s,
                     destination_x, destination_y)

        return path

    def arrowCalc(self, start_point=None, end_point=None):  # calculates the point where the arrow should be drawn

        try:
            startPoint, endPoint = start_point, end_point

            if start_point is None:
                startPoint = self._sourcePoint

            if endPoint is None:
                endPoint = self._destinationPoint

            dx, dy = startPoint.x() - endPoint.x(), startPoint.y() - endPoint.y()

            leng = math.sqrt(dx ** 2 + dy ** 2)
            normX, normY = dx / leng, dy / leng  # normalize

            # perpendicular vector
            perpX = -normY
            perpY = normX

            leftX = endPoint.x() + self._arrow_height * normX + self._arrow_width * perpX
            leftY = endPoint.y() + self._arrow_height * normY + self._arrow_width * perpY

            rightX = endPoint.x() + self._arrow_height * normX - self._arrow_height * perpX
            rightY = endPoint.y() + self._arrow_height * normY - self._arrow_width * perpY

            point2 = QtCore.QPointF(leftX, leftY)
            point3 = QtCore.QPointF(rightX, rightY)

            return QtGui.QPolygonF([point2, endPoint, point3])

        except (ZeroDivisionError, Exception):
            return None

    def paint(self, painter: QtGui.QPainter, option, widget=None) -> None:

        painter.setRenderHint(painter.Antialiasing)

        painter.pen().setWidth(2)
        painter.setBrush(QtCore.Qt.NoBrush)

        # path = self.directPath()
        # path = self.bezierPath()
        path = self.squarePath()
        painter.drawPath(path)
        self.setPath(path)

        triangle_source = self.arrowCalc(path.pointAtPercent(0.1), self._sourcePoint)  # change path.PointAtPercent() value to move arrow on the line

        if triangle_source is not None:
            painter.drawPolyline(triangle_source)


class ViewPort(QtWidgets.QGraphicsView):

    def __init__(self):
        super(ViewPort, self).__init__()

        self.setViewportUpdateMode(self.FullViewportUpdate)

        self._isdrawingPath = False
        self._current_path = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:

        if event.button() == QtCore.Qt.LeftButton:

            pos = self.mapToScene(event.pos())
            self._isdrawingPath = True
            self._current_path = Path(source=pos, destination=pos)
            self.scene().addItem(self._current_path)

            return

        super(ViewPort, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):

        pos = self.mapToScene(event.pos())

        if self._isdrawingPath:
            self._current_path.setDestination(pos)
            self.scene().update(self.sceneRect())
            return

        super(ViewPort, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:

        pos = self.mapToScene(event.pos())

        if self._isdrawingPath:
            self._current_path.setDestination(pos)
            self._isdrawingPath = False
            self._current_path = None
            self.scene().update(self.sceneRect())
            return

        super(ViewPort, self).mouseReleaseEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = ViewPort()
    scene = QtWidgets.QGraphicsScene()
    window.setScene(scene)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
