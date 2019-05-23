import sys
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
import smopy
from PIL.ImageQt import ImageQt, Image
import urllib
import io
import math


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile


def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def getImageCluster(lat_deg, lon_deg, delta_lat, delta_long, zoom):
    smurl = r"http://a.tile.openstreetmap.org/{0}/{1}/{2}.png"
    xmin, ymax = deg2num(lat_deg, lon_deg, zoom)
    xmax, ymin = deg2num(lat_deg + delta_lat, lon_deg + delta_long, zoom)

    Cluster = Image.new('RGB', ((xmax - xmin + 1) * 256 - 1, (ymax - ymin + 1) * 256 - 1))
    for xtile in range(xmin, xmax + 1):
        for ytile in range(ymin, ymax + 1):
            try:
                imgurl = smurl.format(zoom, xtile, ytile)
                print("Opening: " + imgurl)
                imgstr = urllib.urlopen(imgurl).read()
                tile = Image.open(io.StringIO(imgstr))
                Cluster.paste(tile, box=((xtile - xmin) * 256, (ytile - ymin) * 255))
            except:
                print("Couldn't download image")
                tile = None

    return Cluster


class MapWidget(QGraphicsRectItem):

    def __init__(self, scene, parent, lat0=42, lat1=-1, lon0=55, lon1=3, zoom=3):
        super(MapWidget, self).__init__(parent)

        self.scene = scene
        self.setRect(0.0, 0.0, 800, 600)
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.image = None
        self.img = None

        self.scene.addItem(self)

        self.lat0 = lat0
        self.lat1 = lat1
        self.lon0 = lon0
        self.lon1 = lon1
        self.zoom = zoom

        self.load_map()

    def load_map(self, lat0=42, lat1=-1, lon0=55, lon1=3, zoom=3):
        """
        Load a map image into the widget
        :param lat0:
        :param lat1:
        :param lon0:
        :param lon1:
        :param zoom: 1~14
        """
        # store coordinates
        self.lat0 = lat0
        self.lat1 = lat1
        self.lon0 = lon0
        self.lon1 = lon1
        self.zoom = zoom

        # get map
        map = smopy.Map((lat0, lat1, lon0, lon1), z=zoom)

        w, h = map.img.size
        self.img = ImageQt(map.img)
        self.image = QPixmap.fromImage(self.img)

        # resize widget
        self.setRect(0.0, 0.0, w, h)

    def paint(self, painter, option, widget=None):
        """
        Action that happens on widget repaint
        :param painter:
        :param option:
        :param widget:
        """
        painter.drawPixmap(QPoint(0, 0), self.image)
        self.scene.update()


class Window(QDialog):

    def __init__(self):
        super(Window, self).__init__()

        self.layout = QVBoxLayout(self)

        self.view = QGraphicsView()

        self.scene = QGraphicsScene()

        self.view.setScene(self.scene)

        self.layout.addWidget(self.view)

        self.map = MapWidget(self.scene)

        self.resize(1200, 800)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())

