import sys
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
import smopy


class MapWidget(QGraphicsPixmapItem):
    def __init__(self, parent=None):
        super(MapWidget, self).__init__(parent)
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)

        # get map
        map = smopy.Map((37, -3), z=11, tilesize=48)
        numpy_image = map.to_numpy()
        img = QImage(numpy_image.data, *numpy_image.shape[1::-1], QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(img))


class Window(QDialog):
    def __init__(self):
        super(Window, self).__init__()

        self.layout = QVBoxLayout(self)
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

        self.layout.addWidget(self.view)

        self.map = MapWidget()
        self.scene.addItem(self.map)
        self.resize(1200, 800)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())