from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsView, QApplication
import sys

class MyGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super(MyGraphicsView, self).__init__(parent)

        scene = QGraphicsScene(self)
        self.setScene(scene)

        line = QGraphicsLineItem(0, 0, 100, 100)
        pen = line.pen()
        pen.setWidth(5)
        pen.setCapStyle(Qt.RoundCap)  # Use Qt.RoundCap for round line cap
        line.setPen(pen)

        scene.addItem(line)

def main():
    app = QApplication(sys.argv)
    view = MyGraphicsView()
    view.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()