from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsRectItem, \
    QApplication
from PySide6.QtGui import QPen
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter
import sys
import math


def draw_concentric_lines_with_circles(scene, center, N, radius_large, radius_small, line_length):
    angle_step = 360 / N
    for i in range(N):
        angle_deg = -90 + i * angle_step
        angle_rad = math.radians(angle_deg)

        # Direction vector
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)

        # Line end point
        end_x = center.x() + dx * line_length
        end_y = center.y() + dy * line_length

        # Draw line
        line = QGraphicsLineItem(center.x(), center.y(), end_x, end_y)
        line.setPen(QPen(Qt.GlobalColor.black, 1))
        scene.addItem(line)

        # Point for large circle center
        circle_center_x = center.x() + dx * radius_large
        circle_center_y = center.y() + dy * radius_large

        # Draw large circle (centered)
        large_circle = QGraphicsEllipseItem(
            circle_center_x - radius_large,
            circle_center_y - radius_large,
            2 * radius_large,
            2 * radius_large
        )
        large_circle.setPen(QPen(Qt.blue, 1))
        scene.addItem(large_circle)

        # Compute offset to make small circle tangent and centered on the same line
        tangent_center_distance = 2 * radius_large + radius_small
        small_circle_center_x = center.x() + dx * tangent_center_distance
        small_circle_center_y = center.y() + dy * tangent_center_distance

        # Draw small circle
        small_circle = QGraphicsEllipseItem(
            small_circle_center_x - radius_small,
            small_circle_center_y - radius_small,
            2 * radius_small,
            2 * radius_small
        )
        small_circle.setPen(QPen(Qt.red, 1))
        scene.addItem(small_circle)


# === Main Application ===

app = QApplication(sys.argv)

scene = QGraphicsScene()
view = QGraphicsView(scene)
view.setRenderHint(QPainter.Antialiasing)

# Add bounding box rect (optional)
rect = QGraphicsRectItem(0, 0, 400, 400)
rect.setPen(QPen(Qt.gray, 1, Qt.DashLine))
scene.addItem(rect)

# Center of scene
center = QPointF(200, 200)

# Draw elements
draw_concentric_lines_with_circles(
    scene=scene,
    center=center,
    N=5,
    radius_large=30,
    radius_small=10,
    line_length=150
)

view.setWindowTitle("Concentric Lines with Circles")
view.resize(500, 500)
view.show()
sys.exit(app.exec())
