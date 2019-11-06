# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

# Declare colors
ACTIVE = {'style': Qt.SolidLine, 'color': Qt.black}
DEACTIVATED = {'style': Qt.DashLine, 'color': Qt.gray}
EMERGENCY = {'style': Qt.SolidLine, 'color': Qt.yellow}
OTHER = ACTIVE
FONT_SCALE = 1.9


class LineUpdateMixin(object):

    def __init__(self, parent):
        super(LineUpdateMixin, self).__init__(parent)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_line(value)
        return super(LineUpdateMixin, self).itemChange(change, value)


class Polygon(LineUpdateMixin, QGraphicsPolygonItem):
    pass


class Square(LineUpdateMixin, QGraphicsRectItem):
    pass


class Circle(LineUpdateMixin, QGraphicsEllipseItem):
    pass


class QLine(LineUpdateMixin, QGraphicsLineItem):
    pass


class GeneralItem(object):

    def __init__(self):
        self.color = ACTIVE['color']
        self.width = 2
        self.style = ACTIVE['style']
        self.setBrush(QBrush(Qt.darkGray))
        self.setPen(QPen(self.color, self.width, self.style))

    def editParameters(self):
        pd = ParameterDialog(self.window())
        pd.exec_()

    def contextMenuEvent(self, event):
        menu = QMenu()

        ra3 = menu.addAction('Delete all the connections')
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove_)

        menu.exec_(event.screenPos())

    def rotate_clockwise(self):
        self.rotate(90)

    def rotate_counterclockwise(self):
        self.rotate(-90)

    def rotate(self, angle):

        pass

    def delete_all_connections(self):

        self.terminal.remove_all_connections()

    def remove_(self):
        """

        @return:
        """
        self.delete_all_connections()


class ParameterDialog(QDialog):

    def __init__(self, parent=None):
        super(ParameterDialog, self).__init__(parent)
        self.button = QPushButton('Ok', self)
        l = QVBoxLayout(self)
        l.addWidget(self.button)
        self.button.clicked.connect(self.OK)

    def OK(self):
        self.close()