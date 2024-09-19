from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsScene, QGraphicsView, QApplication
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtGui import QPen, QPolygonF, QPainter
import math
import sys


class DraggableNode(QGraphicsEllipseItem):
    def __init__(self, x, y, radius=10, parent=None):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius, parent)
        self.setBrush(Qt.blue)
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable)
        self.setPos(x, y)
        self.radius = radius


class PowerLineItem(QGraphicsLineItem):
    def __init__(self, start_node, end_node, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node
        self.pen = QPen(Qt.black, 2)
        self.setPen(self.pen)
        self.arrow_size = 10
        self.update_line()

    def update_line(self):
        """Update the line to match the current position of the nodes."""
        start_pos = self.start_node.pos() + QPointF(self.start_node.radius, self.start_node.radius)
        end_pos = self.end_node.pos() + QPointF(self.end_node.radius, self.end_node.radius)
        self.setLine(QLineF(start_pos, end_pos))
        self.update()  # Trigger redraw of the arrows

    def draw_arrow(self, painter, start, end, above=True):
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_offset_angle = math.pi / 2 if above else -math.pi / 2

        arrow_start = QPointF(
            start.x() + self.arrow_size * math.cos(angle + arrow_offset_angle),
            start.y() + self.arrow_size * math.sin(angle + arrow_offset_angle)
        )
        arrow_end = QPointF(
            end.x() + self.arrow_size * math.cos(angle + arrow_offset_angle),
            end.y() + self.arrow_size * math.sin(angle + arrow_offset_angle)
        )

        painter.drawLine(arrow_start, arrow_end)
        self.draw_arrowhead(painter, arrow_end, angle)

    def draw_arrowhead(self, painter, point, angle):
        arrow_head_size = self.arrow_size / 2
        left = QPointF(
            point.x() + arrow_head_size * math.cos(angle + math.pi - math.pi / 6),
            point.y() + arrow_head_size * math.sin(angle + math.pi - math.pi / 6)
        )
        right = QPointF(
            point.x() + arrow_head_size * math.cos(angle + math.pi + math.pi / 6),
            point.y() + arrow_head_size * math.sin(angle + math.pi + math.pi / 6)
        )

        arrow_head = QPolygonF([point, left, right])
        painter.setBrush(Qt.black)
        painter.drawPolygon(arrow_head)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        start = self.line().p1()
        end = self.line().p2()

        # Draw active power arrows above the line
        self.draw_arrow(painter, start, end, above=True)  # "From" side active power
        self.draw_arrow(painter, end, start, above=True)  # "To" side active power

        # Draw reactive power arrows below the line
        self.draw_arrow(painter, start, end, above=False)  # "From" side reactive power
        self.draw_arrow(painter, end, start, above=False)  # "To" side reactive power


class SceneWithNodes(QGraphicsScene):
    def __init__(self):
        super().__init__()
        # Create two draggable nodes
        self.start_node = DraggableNode(50, 50)
        self.end_node = DraggableNode(300, 200)
        self.addItem(self.start_node)
        self.addItem(self.end_node)

        # Create the line item connecting the two nodes
        self.power_line = PowerLineItem(self.start_node, self.end_node)
        self.addItem(self.power_line)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # Update the line as the nodes are dragged
        self.power_line.update_line()


# Main application
def main():
    app = QApplication(sys.argv)
    scene = SceneWithNodes()

    view = QGraphicsView(scene)
    view.setRenderHint(view.renderHints() | QPainter.Antialiasing)
    view.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
