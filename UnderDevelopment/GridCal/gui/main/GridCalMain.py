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

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of GridCal.
"""

import os.path
import platform
import sys
from collections import OrderedDict
from enum import Enum

from PyQt5.QtCore import *
from grid.CircuitOO import *
from gui.main.gui import *
from matplotlib.colors import LinearSegmentedColormap
from multiprocessing import cpu_count
from gui.GuiFunctions import *


class GeneralItem(object):

    def editParameters(self):
        pd = ParameterDialog(self.window())
        pd.exec_()

    def contextMenuEvent(self, event):
        menu = QMenu()
        pa = menu.addAction('Parameters')
        pa.triggered.connect(self.editParameters)

        ra1 = menu.addAction('Rotate +90')
        ra1.triggered.connect(self.rotate_clockwise)
        ra2 = menu.addAction('Rotate -90')
        ra2.triggered.connect(self.rotate_counterclockwise)

        ra3 = menu.addAction('Delete all the connections')
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove_)

        menu.exec_(event.screenPos())

    def rotate_clockwise(self):
        self.rotate(90)

    def rotate_counterclockwise(self):
        self.rotate(-90)

    def delete_all_connections(self):
        for term in self.terminals:
            term.remove_all_connections()
        # for term in self.lower_terminals:
        #     term.remove_all_connections()

    def remove_(self, delete_in_API=True):
        """

        @param delete_in_API:
        @return:
        """
        self.delete_all_connections()


class BranchGraphicItem(QGraphicsLineItem):
    """
    - fromPort
    - toPort
    """
    def __init__(self, fromPort, toPort, diagramScene, width=5, branch: Branch=None):
        """

        @param fromPort:
        @param toPort:
        @param diagramScene:
        """
        QGraphicsLineItem.__init__(self, None)

        self.api_object = branch
        if self.api_object is not None:
            if self.api_object.is_enabled:
                self.style = Qt.SolidLine
                self.color = QtCore.Qt.black
            else:
                self.style = Qt.DashLine
                self.color = QtCore.Qt.gray
        else:
            self.style = Qt.SolidLine
            self.color = QtCore.Qt.black
        self.width = width
        self.pen_width = width
        self.setPen(QtGui.QPen(QtCore.Qt.black, self.width, self.style))
        self.setFlag(self.ItemIsSelectable, True)

        self.pos1 = None
        self.pos2 = None
        self.fromPort = None
        self.toPort = None
        self.diagramScene = diagramScene

        if fromPort:
            self.setFromPort(fromPort)

        if toPort:
            self.setToPort(toPort)

        # Create arrow item:
        # self.line_object = LineItem(self)
        self.diagramScene.addItem(self)

        if fromPort and toPort:
            self.redraw()

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        menu = QMenu()

        ra1 = menu.addAction('Properties')
        ra1.triggered.connect(self.editParameters)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        menu.addSeparator()

        ra2 = menu.addAction('Delete')
        ra2.triggered.connect(self.remove)

        menu.exec_(event.screenPos())

    def editParameters(self):
        """
        Display parameters editor for the Bus
        :return:
        """
        dialogue = QDialog(parent=self.diagramScene.parent())
        dialogue.setWindowTitle(self.api_object.name)
        layout = QVBoxLayout()
        grid = QTableView()
        layout.addWidget(grid)
        dialogue.setLayout(layout)

        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.edit_types,
                           parent=grid, editable=True, transposed=True, non_editable_indices=[1, 2])

        grid.setModel(mdl)
        dialogue.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True,
                           non_editable_indices=[1, 2])

        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def remove(self):
        """
        Remove this object in the diagram and the API
        @return:
        """
        self.diagramScene.circuit.delete_branch(self.api_object)
        self.diagramScene.removeItem(self)

    def remove_(self):
        """
        Remove this object in the diagram
        @return:
        """
        self.diagramScene.removeItem(self)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.is_enabled:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.is_enabled = val
        if self.api_object is not None:
            if self.api_object.is_enabled:
                self.style = Qt.SolidLine
                self.color = QtCore.Qt.black
            else:
                self.style = Qt.DashLine
                self.color = QtCore.Qt.gray
        else:
            self.style = Qt.SolidLine
            self.color = QtCore.Qt.black
        self.setPen(QtGui.QPen(self.color, self.width, self.style))

    def setFromPort(self, fromPort):
        """
        Set the From terminal in a connection
        @param fromPort:
        @return:
        """
        self.fromPort = fromPort
        if self.fromPort:
            self.pos1 = fromPort.scenePos()
            self.fromPort.posCallbacks.append(self.setBeginPos)
            self.fromPort.setZValue(0)

    def setToPort(self, toPort):
        """
        Set the To terminal in a connection
        @param toPort:
        @return:
        """
        self.toPort = toPort
        if self.toPort:
            self.pos2 = toPort.scenePos()
            self.toPort.posCallbacks.append(self.setEndPos)
            self.toPort.setZValue(0)

    def setEndPos(self, endpos):
        """
        Set the starting position
        @param endpos:
        @return:
        """
        self.pos2 = endpos
        self.redraw()

    def setBeginPos(self, pos1):
        """
        Set the starting position
        @param pos1:
        @return:
        """
        self.pos1 = pos1
        self.redraw()

    def redraw(self):
        """
        Redraw the line with the given positions
        @return:
        """
        self.setLine(QLineF(self.pos1, self.pos2))
        self.setZValue(0)


class ParameterDialog(QDialog):

    def __init__(self, parent=None):
        super(ParameterDialog, self).__init__(parent)
        self.button = QPushButton('Ok', self)
        l = QVBoxLayout(self)
        l.addWidget(self.button)
        self.button.clicked.connect(self.OK)

    def OK(self):
        self.close()


class TerminalItem(QGraphicsEllipseItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self, name, editor=None, parent=None, h=10, w=10):
        """

        @param name:
        @param editor:
        @param parent:
        """
        QGraphicsEllipseItem.__init__(self, QRectF(-6, -6, h, w), parent)
        self.setCursor(QCursor(QtCore.Qt.CrossCursor))

        # Properties:
        self.setBrush(QBrush(Qt.white))

        # terminal parent object
        self.parent = parent

        self.hosting_connections = list()

        self.editor = editor

        # Name:
        self.name = name
        self.posCallbacks = []
        self.setFlag(self.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        """

        @param change:
        @param value:
        @return:
        """
        if change == self.ItemScenePositionHasChanged:
            for cb in self.posCallbacks:
                cb(value)
            return value
        return super(TerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Start a connection
        Args:
            event:

        Returns:

        """
        self.editor.startConnection(self)
        self.hosting_connections.append(self.editor.startedConnection)

    def remove_all_connections(self):
        """
        Removes all the terminal connections
        Returns:

        """
        n = len(self.hosting_connections)
        for i in range(n-1, -1, -1):
            self.hosting_connections[i].remove_()
            self.hosting_connections.pop(i)


class HandleItem(QGraphicsEllipseItem):
    """
    A handle that can be moved by the mouse: Element to resize the boxes
    """
    def __init__(self, parent=None):
        """

        @param parent:
        """
        QGraphicsEllipseItem.__init__(self, QRectF(-4, -4, 8, 8), parent)
        # super(HandleItem, self).__init__(QRectF(-4, -4, 8, 8), parent)
        self.posChangeCallbacks = []
        self.setBrush(QtGui.QBrush(Qt.red))
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsScenePositionChanges, True)
        self.setCursor(QtGui.QCursor(Qt.SizeFDiagCursor))

    def itemChange(self, change, value):
        """

        @param change:
        @param value:
        @return:
        """
        if change == self.ItemPositionChange:
            x, y = value.x(), value.y()
            # TODO: make this a signal?
            # This cannot be a signal because this is not a QObject
            for cb in self.posChangeCallbacks:
                res = cb(x, y)
                if res:
                    x, y = res
                    value = QPointF(x, y)
            return value

        # Call superclass method:
        return super(HandleItem, self).itemChange(change, value)


class LoadGraphicItem(QGraphicsPolygonItem):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        QGraphicsPolygonItem.__init__(self, parent=parent)

        self.w = 60.0
        self.h = 60.0

        self.api_object = api_obj

        self.diagramScene = diagramScene

        # Properties of the rectangle:
        self.setPen(QtGui.QPen(QtCore.Qt.red, 2))
        # self.setBrush(QtGui.QBrush(QtCore.Qt.black))
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        pts = [QPointF(0, 0), QPointF(20, 0), QPointF(10, 20)]
        self.setPolygon(QtGui.QPolygonF(pts))

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self)
        self.api_object.bus.loads.remove(self.api_object)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)


class BusGraphicItem(QGraphicsRectItem, GeneralItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """
    def __init__(self, diagramScene, name='Untitled', parent=None, index=0, editor=None,
                 bus: Bus=None, pos: QPoint=None):
        """

        @param diagramScene:
        @param name:
        @param parent:
        @param index:
        @param editor:
        """
        QGraphicsRectItem.__init__(self, parent=parent)
        GeneralItem.__init__(self)

        self.w = 60.0
        self.h = 60.0

        self.api_object = bus

        self.diagramScene = diagramScene

        self.editor = editor

        # Properties of the rectangle:
        self.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        self.setBrush(QtGui.QBrush(QtCore.Qt.black))
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        # index
        self.index = index

        if pos is not None:
            self.setPos(pos)

        # Label:
        self.label = QGraphicsTextItem(bus.name, self)
        self.label.setDefaultTextColor(QtCore.Qt.white)

        # Create corner for resize:
        self.sizer = HandleItem(self)
        self.sizer.setPos(self.w, self.h)
        self.sizer.posChangeCallbacks.append(self.changeSize)  # Connect the callback

        self.sizer.setFlag(self.sizer.ItemIsSelectable, True)

        # connection terminals the block:
        self.upper_terminals = []
        self.upper_terminals.append(TerminalItem('n', parent=self, editor=self.editor))  # , h=self.h))
        self.lower_terminals = []
        self.lower_terminals.append(TerminalItem('s', parent=self, editor=self.editor))  # , h=self.h))
        self.right_terminals = []
        self.right_terminals.append(TerminalItem('e', parent=self, editor=self.editor))  # , w=self.w))
        self.left_terminals = []
        self.left_terminals.append(TerminalItem('w', parent=self, editor=self.editor))  # , w=self.w))

        self.terminals = self.upper_terminals + self.lower_terminals + self.right_terminals + self.left_terminals

        # Update size:
        self.changeSize(self.w, self.h)

    def changeSize(self, w, h):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        if h < self.h:
            h = self.h
        if w < self.w:
            w = self.w
        self.setRect(0.0, 0.0, w, h)

        offset = 10

        # center label:
        rect = self.label.boundingRect()
        lw, lh = rect.width(), rect.height()
        lx = (w - lw) / 2
        ly = (h - lh) / 2
        self.label.setPos(lx, ly)

        # upper
        n = len(self.upper_terminals)
        y0 = -offset/2
        dx = w / (n+1)
        x0 = dx
        for term in self.upper_terminals:
            term.setPos(x0, y0)
            # term.setPos(x0 - w / 2 + offset / 2, y0)
            x0 += dx

        # lower
        n = len(self.lower_terminals)
        y0 = h + offset
        dx = w / (n+1)
        x0 = dx
        for term in self.lower_terminals:
            term.setPos(x0, y0)
            # term.setPos(x0 - w / 2 + offset / 2, y0)
            x0 += dx

        # right
        n = len(self.right_terminals)
        x0 = w + offset
        dy = h / (n+1)
        y0 = dy
        for term in self.right_terminals:
            term.setPos(x0, y0)
            # term.setPos(x0, y0 - h / 2 + offset / 2)
            y0 += dy

        # left
        n = len(self.left_terminals)
        x0 = - offset
        dy = h / (n+1)
        y0 = dy
        for term in self.left_terminals:
            term.setPos(x0, y0)
            # term.setPos(x0, y0 - h / 2 + offset / 2)
            y0 += dy

        return w, h

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        # pa = menu.addAction('Parameters')
        # pa.triggered.connect(self.editParameters)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pl = menu.addAction('Plot profiles')
        pl.triggered.connect(self.plot_profiles)

        ra1 = menu.addAction('Rotate +90')
        ra1.triggered.connect(self.rotate_clockwise)
        ra2 = menu.addAction('Rotate -90')
        ra2.triggered.connect(self.rotate_counterclockwise)

        menu.addSeparator()

        ra3 = menu.addAction('Delete all the connections')
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        al = menu.addAction('Add load')
        al.triggered.connect(self.add_load)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.delete_all_connections()
        self.diagramScene.removeItem(self)
        self.diagramScene.circuit.delete_bus(self.api_object)

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        self.api_object.is_enabled = not self.api_object.is_enabled
        print('Enabled:', self.api_object.is_enabled)

        if self.api_object.is_enabled:
            self.setBrush(QtGui.QBrush(QtCore.Qt.black))

            for term in self.terminals:
                for host in term.hosting_connections:
                    host.set_enable(val=True)
        else:
            self.setBrush(QtGui.QBrush(QtCore.Qt.gray))

            for term in self.terminals:
                for host in term.hosting_connections:
                    host.set_enable(val=False)

    def plot_profiles(self):
        """

        @return:
        """
        # t = self.diagramScene.circuit.master_time_array
        # self.api_object.plot_profiles(time_idx=t)
        self.api_object.plot_profiles()

    def editParameters(self):
        """
        Display parameters editor for the Bus
        :return:
        """
        dialogue = QDialog(parent=self.diagramScene.parent())
        dialogue.setWindowTitle(self.api_object.name)
        layout = QVBoxLayout()
        grid = QTableView()
        layout.addWidget(grid)
        dialogue.setLayout(layout)

        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.edit_types,
                           parent=grid, editable=True, transposed=True)

        grid.setModel(mdl)
        dialogue.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def add_load(self):

        load_obj = Load()
        load_obj.bus = self.api_object
        load_grph = LoadGraphicItem(self, load_obj, self.diagramScene)
        load_obj.graphic_obj = load_grph
        self.api_object.loads.append(load_obj)


class EditorGraphicsView(QGraphicsView):
    """
    Editor where the diagram is displayed
    """
    def __init__(self, scene, parent=None, editor=None):
        """

        @param scene:
        @param parent:
        @param editor:
        """
        QGraphicsView.__init__(self, scene, parent)

        # self.setBackgroundBrush(QColor(0,66,255,180))
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setMouseTracking(True)
        self.scene_ = scene
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.editor = editor
        self.last_n = 1
        self.setAlignment(Qt.AlignCenter)

    def dragEnterEvent(self, event):
        """

        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dragMoveEvent(self, event):
        """
        Move element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dropEvent(self, event):
        """
        Create an element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            objtype = event.mimeData().data('component/name')
            # name = str(objtype)

            print(str(event.mimeData().data('component/name')))

            elm = None
            data = QByteArray()
            stream = QDataStream(data, QIODevice.WriteOnly)
            stream.writeQString('Bus')
            if objtype == data:
                name = 'Bus ' + str(self.last_n)
                self.last_n += 1
                obj = Bus(name=name)
                elm = BusGraphicItem(diagramScene=self.scene(), name=name, editor=self.editor, bus=obj)
                obj.graphic_obj = elm
                self.scene_.circuit.add_bus(obj)  # weird but only way to have graphical-API communication

            if elm is not None:
                elm.setPos(self.mapToScene(event.pos()))
                self.scene_.addItem(elm)
                # self.scene_.circuit.add_bus(obj) # weird but only way to have graphical-API communication
                print('Block created')

    def wheelEvent(self, event):
        """
        Zoom
        @param event:
        @return:
        """
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Scale the view / do the zoom
        scale_factor = 1.15
        # print(event.angleDelta().x(), event.angleDelta().y(), event.angleDelta().manhattanLength() )
        if event.angleDelta().y() > 0:
            # Zoom in
            self.scale(scale_factor, scale_factor)

        else:
            # Zooming out
            self.scale(1.0 / scale_factor, 1.0 / scale_factor)

    def add_bus(self, bus: Bus, explode_factor=1.0):
        elm = BusGraphicItem(diagramScene=self.scene(), name=bus.name, editor=self.editor, bus=bus)
        elm.setPos(self.mapToScene(QPoint(bus.x * explode_factor, bus.y * explode_factor)))
        self.scene_.addItem(elm)
        return elm


class LibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    """
    def __init__(self, parent=None):
        """

        @param parent:
        """
        QStandardItemModel.__init__(self, parent)

    def mimeTypes(self):
        """

        @return:
        """
        return ['component/name']

    def mimeData(self, idxs):
        """

        @param idxs:
        @return:
        """
        mimedata = QMimeData()
        for idx in idxs:
            if idx.isValid():
                txt = self.data(idx, Qt.DisplayRole)

                data = QByteArray()
                stream = QDataStream(data, QIODevice.WriteOnly)
                stream.writeQString(txt)

                mimedata.setData('component/name', data)
        return mimedata


class DiagramScene(QGraphicsScene):

    def __init__(self, parent=None, circuit: MultiCircuit=None):
        """

        @param parent:
        """
        super(DiagramScene, self).__init__(parent)
        self.parent_ = parent
        self.circuit = circuit

    def mouseMoveEvent(self, mouseEvent):
        """

        @param mouseEvent:
        @return:
        """
        self.parent_.sceneMouseMoveEvent(mouseEvent)
        super(DiagramScene, self).mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """

        @param mouseEvent:
        @return:
        """
        self.parent_.sceneMouseReleaseEvent(mouseEvent)
        super(DiagramScene, self).mouseReleaseEvent(mouseEvent)


class ObjectFactory(object):

    def get_box(self):
        """

        @return:
        """
        pixmap = QPixmap(40, 40)
        pixmap.fill()
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 40, 40, Qt.black)
        # painter.setBrush(Qt.red)
        # painter.drawEllipse(36, 2, 20, 20)
        # painter.setBrush(Qt.yellow)
        # painter.drawEllipse(20, 20, 20, 20)
        painter.end()

        return QIcon(pixmap)

    def get_circle(self):
        """

        @return:
        """
        pixmap = QPixmap(40, 40)
        pixmap.fill()
        painter = QPainter(pixmap)
        # painter.fillRect(10, 10, 80, 80, Qt.black)
        painter.setBrush(Qt.red)
        painter.drawEllipse(0, 0, 40, 40)
        # painter.setBrush(Qt.yellow)
        # painter.drawEllipse(20, 20, 20, 20)
        painter.end()

        return QIcon(pixmap)

########################################################################################################################
# Main Window
########################################################################################################################


# define the IPython console
print(platform.system())
# if platform.system() == 'Linux':
#     from IPython.qt.console.rich_ipython_widget import RichIPythonWidget
#     from IPython.qt.inprocess import QtInProcessKernelManager
#     from IPython.lib import guisupport
#
#     class QIPythonWidget(RichIPythonWidget):
#         """
#         Convenience class for a live IPython console widget.
#         We can replace the standard banner using the customBanner argument
#         """
#
#         def __init__(self, customBanner=None, *args, **kwargs):
#             if customBanner is not None:
#                 self.banner = customBanner
#             super(QIPythonWidget, self).__init__(*args, **kwargs)
#             self.kernel_manager = kernel_manager = QtInProcessKernelManager()
#             kernel_manager.start_kernel(show_banner=False)
#             kernel_manager.kernel.gui = 'qt4'
#             self.kernel_client = kernel_client = self._kernel_manager.client()
#             kernel_client.start_channels()
#
#             def stop():
#                 kernel_client.stop_channels()
#                 kernel_manager.shutdown_kernel()
#                 guisupport.get_app_qt4().exit()
#
#             self.exit_requested.connect(stop)
#
#         def pushVariables(self, variableDict):
#             """
#             Given a dictionary containing name / value pairs, push those variables
#             to the IPython console widget
#             """
#             self.kernel_manager.kernel.shell.push(variableDict)
#
#         def clearTerminal(self):
#             """
#             Clears the terminal
#             """
#             self._control.clear()
#
#             # self.kernel_manager
#
#         def printText(self, text):
#             """
#             Prints some plain text to the console
#             """
#             self._append_plain_text(text)
#
#         def executeCommand(self, command):
#             """
#             Execute a command in the frame of the console widget
#             """
#             self._execute(command, False)
#
#
# elif platform.system() == 'Windows':
#     from qtconsole.qt import QtGui
#     from qtconsole.rich_jupyter_widget import RichJupyterWidget
#     from qtconsole.inprocess import QtInProcessKernelManager
#
#     class QIPythonWidget(RichJupyterWidget):
#         """
#         Convenience class for a live IPython console widget.
#         We can replace the standard banner using the customBanner argument
#         """
#         def __init__(self, customBanner=None, *args, **kwargs):
#             super(QIPythonWidget, self).__init__(*args, **kwargs)
#
#             if customBanner is not None:
#                 self.banner = customBanner
#
#             self.kernel_manager = kernel_manager = QtInProcessKernelManager()
#             kernel_manager.start_kernel(show_banner=False)
#             kernel_manager.kernel.gui = 'qt4'
#             self.kernel_client = kernel_client = self._kernel_manager.client()
#             kernel_client.start_channels()
#
#             def stop():
#                 kernel_client.stop_channels()
#                 kernel_manager.shutdown_kernel()
#                 guisupport.get_app_qt4().exit()
#             self.exit_requested.connect(stop)
#
#         def pushVariables(self, variableDict):
#             """
#             Given a dictionary containing name / value pairs, push those variables
#             to the IPython console widget
#             """
#             self.kernel_manager.kernel.shell.push(variableDict)
#
#         def clearTerminal(self):
#             """
#             Clears the terminal
#             """
#             self._control.clear()
#
#             # self.kernel_manager
#
#         def printText(self, text):
#             """
#             Prints some plain text to the console
#             """
#             self._append_plain_text(text)
#
#         def executeCommand(self, command):
#             """
#             Execute a command in the frame of the console widget
#             """
#             self._execute(command, False)


class ResultTypes(Enum):
    bus_voltage_per_unit = 1,
    bus_voltage = 2,
    bus_s_v_curve = 3,
    bus_QV_curve = 4,
    bus_active_power = 5,
    bus_reactive_power = 6,
    bus_active_and_reactive_power = 7,
    bus_apparent_power = 8,
    branch_current_per_unit = 9,
    branch_current = 10,
    branch_power_flow_per_unit = 11,
    branch_power_flow = 12,
    branch_losses = 13,
    branches_loading = 14,
    gen_reactive_power_pu = 15,
    gen_reactive_power = 16


class ProfileTypes(Enum):
    Loads = 1,
    Generators = 2


class MainGUI(QMainWindow):

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        QWidget.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        # Declare circuit
        self.circuit = MultiCircuit()

        self.project_directory = None

        # solvers dictionary
        self.solvers_dict = OrderedDict()
        self.solvers_dict['Newton-Raphson [NR]'] = SolverType.NR
        self.solvers_dict['NR Fast decoupled (BX)'] = SolverType.NRFD_BX
        self.solvers_dict['NR Fast decoupled (XB)'] = SolverType.NRFD_XB
        self.solvers_dict['Newton-Raphson-Iwamoto'] = SolverType.IWAMOTO
        self.solvers_dict['Gauss-Seidel'] = SolverType.GAUSS
        self.solvers_dict['Z-Matrix Gauss-Seidel'] = SolverType.ZBUS
        self.solvers_dict['Holomorphic embedding [HELM]'] = SolverType.HELM
        self.solvers_dict['Z-Matrix HELM'] = SolverType.HELMZ
        self.solvers_dict['Continuation NR'] = SolverType.CONTINUATION_NR
        self.solvers_dict['DC approximation'] = SolverType.DC

        lst = list(self.solvers_dict.keys())
        mdl = get_list_model(lst)
        self.ui.solver_comboBox.setModel(mdl)
        self.ui.retry_solver_comboBox.setModel(mdl)

        self.ui.solver_comboBox.setCurrentIndex(0)
        self.ui.retry_solver_comboBox.setCurrentIndex(3)

        ################################################################################################################
        # Declare the schematic editor
        ################################################################################################################

        # Widget layout and child widgets:
        self.horizontalLayout = QHBoxLayout(self)
        splitter = QSplitter(self)
        splitter2 = QSplitter(self)
        self.object_editor_table = QTableView(self)
        self.libraryBrowserView = QListView(self)
        self.libraryModel = LibraryModel(self)
        self.libraryModel.setColumnCount(1)

        # Create an icon with an icon:
        object_factory = ObjectFactory()

        # initialize library of items
        self.libItems = []
        self.libItems.append(QStandardItem(object_factory.get_box(), 'Bus'))
        # self.libItems.append(QtGui.QStandardItem(object_factory.get_circle(), 'Generator'))
        # self.libItems.append( QtGui.QStandardItem(object_factory.get_transformer(), 'Transformer') )
        # self.libItems.append(QtGui.QStandardItem(object_factory.get_box(), 'Line'))
        # self.libItems.append(QtGui.QStandardItem(object_factory.get_box(), 'Battery'))
        # self.libItems.append(QtGui.QStandardItem(object_factory.get_box(), 'External Connection'))
        for i in self.libItems:
            self.libraryModel.appendRow(i)

        # set the objects list
        self.object_types = ['Buses', 'Branches', 'Loads', 'Static Generators',
                             'Controlled Generators', 'Batteries', 'Shunts']
        self.ui.dataStructuresListView.setModel(get_list_model(self.object_types))

        # Actual libraryView object
        self.libraryBrowserView.setModel(self.libraryModel)
        self.libraryBrowserView.setViewMode(self.libraryBrowserView.ListMode)
        self.libraryBrowserView.setDragDropMode(self.libraryBrowserView.DragOnly)

        self.diagramScene = DiagramScene(self, self.circuit)  # scene to add to the QGraphicsView
        self.diagramView = EditorGraphicsView(self.diagramScene, parent=self, editor=self)

        # Add the two objects into a layout
        splitter2.addWidget(self.libraryBrowserView)
        splitter2.addWidget(self.object_editor_table)
        splitter2.setOrientation(Qt.Vertical)
        splitter.addWidget(splitter2)
        splitter.addWidget(self.diagramView)

        self.ui.schematic_layout.addWidget(splitter)
        splitter.setStretchFactor(1, 10)
        self.ui.splitter_8.setStretchFactor(1, 15)

        self.startedConnection = None
        self.branch_editor_count = 1
        self.expand_factor = 1.5

        self.lock_ui = False
        self.ui.progress_frame.setVisible(self.lock_ui)

        self.power_flow = None
        self.monte_carlo = None
        self.time_series = None
        self.voltage_stability = None

        self.available_results_dict = None
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(cpu_count())

        ################################################################################################################
        # Console
        ################################################################################################################

        # self.ipyConsole = QIPythonWidget(customBanner="GridCal console.\n\n"
        #                                               "type gridcalhelp() to see the available specific commands.\n\n"
        #                                               "the following libraries are already loaded:\n"
        #                                               "np: numpy\n"
        #                                               "pd: pandas\n"
        #                                               "plt: matplotlib\n\n")
        # self.ui.console_tab.layout().addWidget(self.ipyConsole)
        # self.ipyConsole.pushVariables({"gridcalhelp": self.print_console_help,
        #                                "np": np, "pd": pd, "plt": plt, "clc": self.clc})

        ################################################################################################################
        # Connections
        ################################################################################################################
        self.ui.actionNew_project.triggered.connect(self.new_project)

        self.ui.actionOpen_file.triggered.connect(self.open_file)

        self.ui.actionSave.triggered.connect(self.save_file)

        self.ui.actionPower_flow.triggered.connect(self.run_power_flow)

        self.ui.actionVoltage_stability.triggered.connect(self.run_voltage_stability)

        self.ui.actionPower_Flow_Time_series.triggered.connect(self.run_time_series)

        self.ui.actionPower_flow_Stochastic.triggered.connect(self.run_stochastic)

        self.ui.actionAbout.triggered.connect(self.about_box)

        self.ui.cancelButton.clicked.connect(self.set_cancel_state)

        # node size
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)

        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)

        self.ui.actionCenter_view.triggered.connect(self.center_nodes)

        # list clicks
        self.ui.result_listView.clicked.connect(self.update_available_results_in_the_study)
        self.ui.result_type_listView.clicked.connect(self.result_type_click)

        self.ui.dataStructuresListView.clicked.connect(self.view_objects_data)

        ################################################################################################################
        # Other actions
        ################################################################################################################
        fname = 'IEEE_30BUS_profiles.xls'
        self.circuit.load_file(fname)
        self.create_schematic_from_api(explode_factor=50)

        ################################################################################################################
        # Colormaps
        ################################################################################################################
        vmax = 1.2
        seq = [(0 / vmax, 'black'),
               (0.8 / vmax, 'blue'),
               (1.0 / vmax, 'green'),
               (1.05 / vmax, 'orange'),
               (1.2 / vmax, 'red')]
        self.voltage_cmap = LinearSegmentedColormap.from_list('vcolors', seq)
        seq = [(0.0, 'green'),
               (0.8, 'orange'),
               (1.0, 'red')]
        self.loading_cmap = LinearSegmentedColormap.from_list('lcolors', seq)

    def LOCK(self, val=True):
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        self.ui.progress_frame.setVisible(self.lock_ui)

    def UNLOCK(self):
        """
        Unloack the interface
        @return:
        """
        self.LOCK(False)

    def about_box(self):

        url = 'https://github.com/SanPen/GridCal'

        msg = "GridCal is a research oriented electrical grid calculation software.\n"
        msg += "GridCal has been designed by Santiago Peñate Vera since 2015.\n"
        msg += "The calculation engine has been designed in a fully object oriented fashion. " \
               "The power flow routines have been adapted from MatPower, enhancing them to run fast in " \
               "the object oriented scheme.\n\n"

        msg += "The source of Gridcal can be found at:\n" + url + "\n"

        QtGui.QMessageBox.about(self, "About GridCal", msg)

    def print_console_help(self):
        """
        print the console help in the console
        @return:
        """
        print('GridCal internal commands.\n')
        print('If a command is unavailable is because the study has not been executed yet.')

        print('\n\nclc():\tclear the console.')

        print('\n\nPower flow commands:')
        print('\tpowerflow.voltage:\t the nodal voltages in per unit')
        print('\tpowerflow.current:\t the branch currents in per unit')
        print('\tpowerflow.loading:\t the branch loading in %')
        print('\tpowerflow.losses:\t the branch losses in per unit')
        print('\tpowerflow.power:\t the nodal power injections in per unit')
        print('\tpowerflow.power_from:\t the branch power injections in per unit at the "from" side')
        print('\tpowerflow.power_to:\t the branch power injections in per unit at the "to" side')

        print('\n\nTime series power flow commands:')
        print('\ttimeseries.time:\t Profiles time index (pandas DateTimeIndex object)')
        print('\ttimeseries.load_profiles:\t Load profiles matrix (row: time, col: node)')
        print('\ttimeseries.gen_profiles:\t Generation profiles matrix (row: time, col: node)')
        print('\ttimeseries.voltages:\t nodal voltages results matrix (row: time, col: node)')
        print('\ttimeseries.currents:\t branches currents results matrix (row: time, col: branch)')
        print('\ttimeseries.loadings:\t branches loadings results matrix (row: time, col: branch)')
        print('\ttimeseries.losses:\t branches losses results matrix (row: time, col: branch)')

        print('\n\nVoltage stability power flow commands:')
        print('\tvoltagestability.continuation_voltage:\t Voltage values for every power multiplication factor.')
        print('\tvoltagestability.continuation_lambda:\t Value of power multiplication factor applied')
        print('\tvoltagestability.continuation_power:\t Power values for every power multiplication factor.')

        print('\n\nMonte Carlo power flow commands:')
        print('\tstochastic.V_avg:\t nodal voltage average result.')
        print('\tstochastic.I_avg:\t branch current average result.')
        print('\tstochastic.Loading_avg:\t branch loading average result.')
        print('\tstochastic.Losses_avg:\t branch losses average result.')

        print('\tstochastic.V_std:\t nodal voltage standard deviation result.')
        print('\tstochastic.I_std:\t branch current standard deviation result.')
        print('\tstochastic.Loading_std:\t branch loading standard deviation result.')
        print('\tstochastic.Losses_std:\t branch losses standard deviation result.')

        print('\tstochastic.V_avg_series:\t nodal voltage average series.')
        print('\tstochastic.V_std_series:\t branch current standard deviation series.')
        print('\tstochastic.error_series:\t Monte Carlo error series (the convergence value).')

    def clc(self):
        """
        Clear the console
        @return:
        """
        self.ipyConsole.clearTerminal()

    def startConnection(self, port):
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.startedConnection = BranchGraphicItem(port, None, self.diagramScene)
        self.startedConnection.bus_from = port.parent
        port.setZValue(0)

    def sceneMouseMoveEvent(self, event):
        """

        @param event:
        @return:
        """
        if self.startedConnection:
            pos = event.scenePos()
            self.startedConnection.setEndPos(pos)

    def sceneMouseReleaseEvent(self, event):
        """
        Finalize the branch creation if its drawing ends in a terminal
        @param event:
        @return:
        """
        # Clear or finnish the started connection:
        if self.startedConnection:
            pos = event.scenePos()
            items = self.diagramScene.items(pos)  # get the item (the terminal) at the mouse position

            for item in items:
                if type(item) is TerminalItem:  # connect only to terminals
                    if item.parent is not self.startedConnection.fromPort.parent:  # forbid connecting to itself

                        # if type(item.parent) is not type(self.startedConnection.fromPort.parent): # forbid same type connections

                        self.startedConnection.setToPort(item)
                        item.hosting_connections.append(self.startedConnection)
                        self.startedConnection.setZValue(1000)
                        self.startedConnection.bus_to = item.parent
                        name = 'Branch ' + str(self.branch_editor_count)
                        obj = Branch(bus_from=self.startedConnection.bus_from.api_object,
                                     bus_to=self.startedConnection.bus_to.api_object,
                                     name=name)
                        obj.graphic_obj = self.startedConnection
                        self.startedConnection.api_object = obj
                        self.circuit.add_branch(obj)

            if self.startedConnection.toPort is None:
                self.startedConnection.remove_()

        self.startedConnection = None

        print('Buses:', len(self.circuit.buses))
        print('Branches:', len(self.circuit.branches))

    def bigger_nodes(self):
        """
        Expand the grid
        @return:
        """
        print('bigger')
        for item in self.diagramScene.items():
            if type(item) is BusGraphicItem:
                x = item.pos().x()
                y = item.pos().y()
                item.setPos(QPointF(x*self.expand_factor, y*self.expand_factor))

    def smaller_nodes(self):
        """
        Contract the grid
        @return:
        """
        print('smaller')
        for item in self.diagramScene.items():
            if type(item) is BusGraphicItem:
                x = item.pos().x()
                y = item.pos().y()
                item.setPos(QPointF(x/self.expand_factor, y/self.expand_factor))

    def center_nodes(self):
        """
        Center the view in the nodes
        @return: Nothing
        """
        self.diagramView.fitInView(self.diagramScene.sceneRect(), Qt.KeepAspectRatio)
        self.diagramView.scale(1.0, 1.0)

    def color_based_of_pf(self, voltage, loading):
        """
        Color the grid based on the results passed
        @param voltage: Nodal Voltages array
        @param loading: Branch loading array
        @return: Nothing
        """
        # color nodes
        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = abs(voltage)
        vnorm = (vabs - vmin) / vrng
        # print(vnorm)
        i = 0
        for bus in self.circuit.buses:
            if bus.is_enabled:
                r, g, b, a = self.voltage_cmap(vnorm[i])
                # print(vnorm[i], '->', r*255, g*255, b*255, a)
                # QColor(r, g, b, alpha)
                bus.graphic_obj.setBrush(QColor(r*255, g*255, b*255, a*255))
                bus.graphic_obj.setToolTip(bus.name + '\n' + 'V=' + str(vabs[i]))
            i += 1

        # color branches
        lnorm = abs(loading)
        lnorm[lnorm == np.inf] = 0
        # print(lnorm)
        i = 0
        for branch in self.circuit.branches:

            w = branch.graphic_obj.pen_width
            if branch.is_enabled:
                style = Qt.SolidLine
                r, g, b, a = self.loading_cmap(lnorm[i])
                color = QColor(r*255, g*255, b*255, a*255)
            else:
                style = Qt.DashLine
                color = Qt.gray

            branch.graphic_obj.setToolTip(branch.name + '\n' + 'loading=' + str(lnorm[i]))
            branch.graphic_obj.setPen(QtGui.QPen(color, w, style))
            i += 1

    def new_project(self):
        """
        Create new grid
        :return:
        """
        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure you want to quit the current grid and create a new one?"
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.circuit = MultiCircuit()
                self.diagramScene.circuit = self.circuit
                self.create_schematic_from_api(explode_factor=500)

            else:
                pass
        else:
            pass

    def open_file(self):
        """
        Open GridCal file
        @return:
        """
        # declare the allowed file types
        files_types = "Excel 97 (*.xls);;Excel (*.xlsx);;DigSILENT (*.dgs);;MATPOWER (*.m)"
        # call dialog to select the file

        filename, type_selected = QFileDialog.getOpenFileName(self, 'Open file', directory=self.project_directory, filter=files_types)

        if len(filename) > 0:
            # store the working directory
            self.project_directory = os.path.dirname(filename)
            print(filename)
            self.circuit = MultiCircuit()
            self.circuit.load_file(filename=filename)
            self.create_schematic_from_api(explode_factor=500)

    def save_file(self):
        """
        Save the circuit case to a file
        """
        # declare the allowed file types
        files_types = "Excel (*.xlsx)"
        # call dialog to select the file
        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file',  self.project_directory, files_types)

        if filename is not "":
            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            extension = dict()
            extension['Excel (*.xlsx)'] = '.xlsx'
            # extension['Numpy Case (*.npz)'] = '.npz'

            if file_extension == '':
                filename = name + extension[type_selected]

            # call to save the file in the circuit
            self.circuit.save_file(filename)

    def create_schematic_from_api(self, explode_factor=1):
        """
        This function explores the API values and draws an schematic layout
        @return:
        """
        # clear all
        self.diagramView.scene_.clear()

        # first create the buses
        for bus in self.circuit.buses:
            # print(bus.x, bus.y)
            bus.graphic_obj = self.diagramView.add_bus(bus=bus, explode_factor=explode_factor)

        for branch in self.circuit.branches:
            terminal_from = branch.bus_from.graphic_obj.lower_terminals[0]
            terminal_to = branch.bus_to.graphic_obj.lower_terminals[0]
            connection = BranchGraphicItem(terminal_from, terminal_to, self.diagramScene, branch=branch)
            terminal_from.hosting_connections.append(connection)
            terminal_to.hosting_connections.append(connection)
            connection.redraw()
            branch.graphic_obj = connection

        # self.diagramView.repaint()
        # self.startedConnection.remove_()

    def view_objects_data(self):

        elm_type = self.ui.dataStructuresListView.selectedIndexes()[0].data()

        # ['Buses', 'Branches', 'Loads', 'Static Generators', 'Controlled Generators', 'Batteries']

        if elm_type == 'Buses':
            elm = Bus()
            mdl = ObjectsModel(self.circuit.buses, elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True)

        elif elm_type == 'Branches':
            elm = Branch(None, None)
            mdl = ObjectsModel(self.circuit.branches, elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1, 2])

        elif elm_type == 'Loads':
            elm = Load()
            mdl = ObjectsModel(self.circuit.get_loads(), elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Static Generators':
            elm = StaticGenerator()
            mdl = ObjectsModel(self.circuit.get_static_generators(), elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Controlled Generators':
            elm = ControlledGenerator()
            mdl = ObjectsModel(self.circuit.get_controlled_generators(), elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Batteries':
            elm = Battery()
            mdl = ObjectsModel(self.circuit.get_batteries(), elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Shunts':
            elm = Shunt()
            mdl = ObjectsModel(self.circuit.get_shunts(), elm.edit_headers, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        self.ui.dataStructureTableView.setModel(mdl)

    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = self.solvers_dict[self.ui.solver_comboBox.currentText()]

        enforce_Q_limits = self.ui.control_Q_checkBox.isChecked()

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0**exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        set_last_solution = self.ui.remember_last_solution_checkBox.isChecked()

        if self.ui.helm_retry_checkBox.isChecked():
            solver_to_retry_with = self.solvers_dict[self.ui.retry_solver_comboBox.currentText()]
        else:
            solver_to_retry_with = None

        dispatch_storage = self.ui.dispatch_storage_checkBox.isChecked()

        ops = PowerFlowOptions(solver_type=solver_type,
                               aux_solver_type=solver_to_retry_with,
                               verbose=False,
                               robust=False,
                               initialize_with_existing_solution=True,
                               dispatch_storage=dispatch_storage,
                               tolerance=tolerance,
                               max_iter=max_iter,
                               control_Q=enforce_Q_limits)

        return ops

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """

        self.LOCK()
        self.circuit.compile()

        options = self.get_selected_power_flow_options()
        self.power_flow = PowerFlow(self.circuit, options)

        # self.power_flow.progress_signal.connect(self.ui.progressBar.setValue)
        # self.power_flow.done_signal.connect(self.UNLOCK)
        # self.power_flow.done_signal.connect(self.post_power_flow)
        #
        # self.power_flow.start()
        self.threadpool.start(self.power_flow)

        self.threadpool.waitForDone()
        self.post_power_flow()

    def post_power_flow(self):
        """
        Run a power flow simulation in a separated thread from the gui
        Returns:

        """
        # update the results in the circuit structures
        print('Post power flow')
        print('Vbus:\n', abs(self.circuit.power_flow_results.voltage))
        print('Sbr:\n', abs(self.circuit.power_flow_results.Sbranch))
        print('ld:\n', abs(self.circuit.power_flow_results.loading))
        self.color_based_of_pf(self.circuit.power_flow_results.voltage, self.circuit.power_flow_results.loading)
        self.update_available_results()
        self.UNLOCK()

    def run_voltage_stability(self):
        print('run_voltage_stability')

    def post_voltage_stability(self):
        self.update_available_results()

    def run_time_series(self):
        """
        Run a time series power flow simulation in a separated thread from the gui
        @return:
        """
        self.LOCK()
        self.circuit.compile()

        if self.circuit.has_time_series:

            options = self.get_selected_power_flow_options()
            self.time_series = TimeSeries(grid=self.circuit, options=options)

            # Set the time series run options
            self.time_series.progress_signal.connect(self.ui.progressBar.setValue)
            self.time_series.done_signal.connect(self.UNLOCK)
            self.time_series.done_signal.connect(self.post_time_series)

            self.time_series.start()

        else:
            msg = 'No time series loaded'
            q = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'GridCal', msg)
            q.setStandardButtons(QtGui.QMessageBox.Ok)
            i = QtGui.QIcon()
            i.addPixmap(QtGui.QPixmap("..."), QtGui.QIcon.Normal)
            q.setWindowIcon(i)
            q.exec_()

    def post_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """
        if self.circuit.time_series_results is not None:
            print('\n\nVoltages:\n')
            print(self.circuit.time_series_results.voltage)
            print(self.circuit.time_series_results.converged)
            print(self.circuit.time_series_results.error)

            # plot(grid.master_time_array, abs(grid.time_series_results.loading)*100)
            # show()
            ts_analysis = TimeSeriesResultsAnalysis(self.circuit.circuits[0].time_series_results)
            voltage = self.circuit.time_series_results.voltage.max(axis=1)
            loading = self.circuit.time_series_results.loading.max(axis=1)
            self.color_based_of_pf(voltage, loading)
            self.update_available_results()
        else:
            print('No results for the time series simulation.')

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """
        print('run_stochastic')

        self.LOCK()
        self.circuit.compile()

        options = self.get_selected_power_flow_options()

        self.monte_carlo = MonteCarlo(self.circuit, options)

        self.monte_carlo.progress_signal.connect(self.ui.progressBar.setValue)
        self.monte_carlo.done_signal.connect(self.UNLOCK)
        self.monte_carlo.done_signal.connect(self.post_stochastic)

        self.monte_carlo.start()

    def post_stochastic(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """
        print('post_stochastic')
        # update the results in the circuit structures
        print('Vbus:\n', abs(self.monte_carlo.results.voltage))
        print('Ibr:\n', abs(self.monte_carlo.results.current))
        print('ld:\n', abs(self.monte_carlo.results.loading))
        self.color_based_of_pf(self.monte_carlo.results.voltage, self.monte_carlo.results.loading)
        self.update_available_results()

    def set_cancel_state(self):
        """
        Cancell whatever's going on
        @return:
        """
        if self.power_flow is not None:
            self.power_flow.cancel()

        if self.monte_carlo is not None:
            self.monte_carlo.cancel()

        if self.time_series is not None:
            self.time_series.cancel()

        if self.voltage_stability is not None:
            self.voltage_stability.cancel()

    def update_available_results(self):
        """

        Returns:

        """
        lst = list()
        self.available_results_dict = dict()
        if self.power_flow is not None:
            lst.append("Power Flow")
            self.available_results_dict["Power Flow"] = self.power_flow.results.available_results

        if self.voltage_stability is not None:
            lst.append("Voltage Stability")
            self.available_results_dict["Power Flow"] = self.voltage_stability.results.available_results

        if self.time_series is not None:
            lst.append("Time Series")
            self.available_results_dict["Time Series"] = self.time_series.results.available_results

        if self.monte_carlo is not None:
            lst.append("Monte Carlo")
            self.available_results_dict["Monte Carlo"] = self.monte_carlo.results.available_results

        mdl = get_list_model(lst)
        self.ui.result_listView.setModel(mdl)

    def update_available_results_in_the_study(self):
        """

        Returns:

        """

        elm = self.ui.result_listView.selectedIndexes()[0].data()
        lst = self.available_results_dict[elm]
        mdl = get_list_model(lst)
        self.ui.result_type_listView.setModel(mdl)

    def result_type_click(self):
        print()
        study = self.ui.result_listView.selectedIndexes()[0].data()
        study_type = self.ui.result_type_listView.selectedIndexes()[0].data()

        if 'Bus' in study_type:
            names = self.circuit.bus_names
        elif 'Branch' in study_type:
            names = self.circuit.branch_names

        mdl = get_list_model(names, checks=True)
        self.ui.result_element_selection_listView.setModel(mdl)

        self.ui.resultsPlot.clear()

        if study == 'Power Flow':
            self.power_flow.results.plot(type=study_type, ax=self.ui.resultsPlot.get_axis(), indices=None, names=names)
        elif study == 'Time Series':
            pass
        elif study == 'Voltage Stability':
            pass
        elif study == 'Monte Carlo':
            pass

        self.ui.resultsPlot.redraw()


def run():
    app = QApplication(sys.argv)
    window = MainGUI()
    window.resize(1.61 * 700, 700)  # golden ratio
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
