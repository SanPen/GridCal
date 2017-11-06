from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from GridCal.grid.CalculationEngine import *
from GridCal.gui.GuiFunctions import *
import sys

'''
Dependencies:

GridEditor
 |
  - EditorGraphicsView (Handles the drag and drop)
 |   |
  ---- DiagramScene
        |
         - MultiCircuit (Calculation engine)
        |
         - Graphic Objects: (BusGraphicItem, BranchGraphicItem, LoadGraphicItem, ...)


The graphic objects need to call the API objects and functions inside the MultiCircuit instance.
To do this the graphic objects call "parent.circuit.<function or object>"
'''

# Declare colors
ACTIVE = {'style': Qt.SolidLine, 'color': Qt.black}
DEACTIVATED = {'style': Qt.DashLine, 'color': Qt.gray}
EMERGENCY = {'style': Qt.SolidLine, 'color': QtCore.Qt.yellow}
OTHER = ACTIVE = {'style': Qt.SolidLine, 'color': Qt.black}


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

    def remove_(self):
        """

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
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.width = width
        self.pen_width = width
        self.setPen(QPen(self.color, self.width, self.style))
        self.setFlag(self.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

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

        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=grid, editable=True, transposed=True, non_editable_indices=[1, 2])

        grid.setModel(mdl)
        dialogue.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
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
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.setPen(QPen(self.color, self.width, self.style))

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
        if self.pos1 is not None and self.pos2 is not None:
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
        self.color = ACTIVE['color']
        self.width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.darkGray)
        self.setPen(QPen(self.color, self.width, self.style))

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
        self.setBrush(Qt.red)
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsScenePositionChanges, True)
        self.setCursor(QCursor(Qt.SizeFDiagCursor))

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


class LoadGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        super(LoadGraphicItem, self).__init__(parent)

        self.w = 20.0
        self.h = 20.0

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        # self.installSceneEventFilter(self)

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        parent.scene().addItem(self.nexus)

        self.width = 2

        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        self.glyph = Polygon(self)
        self.glyph.setPolygon(QPolygonF([QPointF(0, 0), QPointF(self.w, 0), QPointF(self.w / 2, self.h)]))
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.addToGroup(self.glyph)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w/2, pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
        )

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profiles')
        pa.triggered.connect(self.plot)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self.nexus)
        self.diagramScene.removeItem(self)
        self.api_object.bus.loads.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.glyph.setPen(QPen(self.color, self.width, self.style))

    def plot(self):

        fig = plt.figure(figsize=(10, 8))
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312)
        ax3 = fig.add_subplot(313)

        self.api_object.Sprof.plot(ax=ax1, linewidth=1)
        self.api_object.Iprof.plot(ax=ax2, linewidth=1)
        self.api_object.Zprof.plot(ax=ax3, linewidth=1)

        ax1.set_title('Power profile')
        ax2.set_title('Current profile')
        ax3.set_title('Impedance profile')

        ax1.set_ylabel('MVA')
        ax2.set_ylabel('kA')
        ax3.set_ylabel('Ohm (p.u.)')

        plt.subplots_adjust(left=0.12, bottom=0.1, right=0.96, top=0.96, wspace=None, hspace=0.6)

        plt.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)


class ShuntGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        # QGraphicsPolygonItem.__init__(self, parent=parent)
        # QGraphicsItemGroup.__init__(self, parent=parent)
        super(ShuntGraphicItem, self).__init__(parent)

        self.w = 15.0
        self.h = 30.0

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        self.width = 2

        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        pen = QPen(self.color, self.width, self.style)

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        # self.installSceneEventFilter(self)

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        parent.scene().addItem(self.nexus)

        self.lines = list()
        self.lines.append(QLineF(QPointF(self.w/2, 0), QPointF(self.w/2, self.h*0.4)))
        self.lines.append(QLineF(QPointF(0, self.h*0.4), QPointF(self.w, self.h*0.4)))
        self.lines.append(QLineF(QPointF(0, self.h*0.6), QPointF(self.w, self.h*0.6)))
        self.lines.append(QLineF(QPointF(self.w/2, self.h*0.6), QPointF(self.w/2, self.h)))
        self.lines.append(QLineF(QPointF(0, self.h * 1), QPointF(self.w, self.h * 1)))
        self.lines.append(QLineF(QPointF(self.w*0.15, self.h * 1.1), QPointF(self.w*0.85, self.h * 1.1)))
        self.lines.append(QLineF(QPointF(self.w * 0.3, self.h * 1.2), QPointF(self.w * 0.7, self.h * 1.2)))
        for l in self.lines:
            l1 = QLine(self)
            l1.setLine(l)
            l1.setPen(pen)
            self.addToGroup(l1)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w/2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
        )

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profile')
        pa.triggered.connect(self.plot)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self.nexus)
        self.diagramScene.removeItem(self)
        self.api_object.bus.shunts.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        pen = QPen(self.color, self.width, self.style)

        for l in self.childItems():
            l.setPen(pen)

    def plot(self):
        """
        Plot API objects profiles
        """
        fig = plt.figure(figsize=(10, 6))
        ax1 = fig.add_subplot(111)

        if self.api_object.Yprof is not None:
            self.api_object.Yprof.plot(ax=ax1, linewidth=1)

        ax1.set_title('Admittance profile')

        ax1.set_ylabel('S (p.u.)')

        plt.subplots_adjust(left=0.12, bottom=0.1, right=0.96, top=0.96, wspace=None, hspace=0.6)

        plt.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)


class ControlledGeneratorGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        # QGraphicsPolygonItem.__init__(self, parent=parent)
        # QGraphicsItemGroup.__init__(self, parent=parent)

        super(ControlledGeneratorGraphicItem, self).__init__(parent)

        # self.w = 60.0
        # self.h = 60.0

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        self.w = 40
        self.h = 40

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        # self.installSceneEventFilter(self)

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        parent.scene().addItem(self.nexus)

        self.width = 2
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Circle(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('G', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h/4, self.w/4)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w/2, pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
        )

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profiles')
        pa.triggered.connect(self.plot)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self.nexus)
        self.diagramScene.removeItem(self)
        self.api_object.bus.controlled_generators.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)

    def plot(self):
        """
        Plot API objects profiles
        """
        fig = plt.figure(figsize=(10, 8))
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        self.api_object.Pprof.plot(ax=ax1, linewidth=1)
        self.api_object.Vsetprof.plot(ax=ax2, linewidth=1)

        ax1.set_title('Active power profile')
        ax2.set_title('Set voltage profile')

        ax1.set_ylabel('MW')
        ax2.set_ylabel('V (p.u.)')

        plt.subplots_adjust(left=0.12, bottom=0.1, right=0.96, top=0.96, wspace=None, hspace=0.6)

        plt.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)


class StaticGeneratorGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        # QGraphicsPolygonItem.__init__(self, parent=parent)
        # QGraphicsItemGroup.__init__(self, parent=parent)
        super(StaticGeneratorGraphicItem, self).__init__(parent)

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        self.w = 40
        self.h = 40

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        parent.scene().addItem(self.nexus)

        # l1 = QGraphicsLineItem(QLineF(QPointF(self.w/2, 0), QPointF(self.w/2, -10)))
        # l1.setPen(pen)
        # self.addToGroup(l1)

        self.width = 2
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        pen = QPen(self.color, self.width, self.style)

        self.glyph = Square(parent)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('S', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h/4, self.w/4)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w/2, pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
        )

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profile')
        pa.triggered.connect(self.plot)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self.nexus)
        self.diagramScene.removeItem(self)
        self.api_object.bus.static_generators.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)

    def plot(self):
        """
        Plot API objects profiles
        """
        fig = plt.figure(figsize=(10, 6))
        ax1 = fig.add_subplot(111)

        self.api_object.Sprof.plot(ax=ax1, linewidth=1)

        ax1.set_title('Active power profile')

        ax1.set_ylabel('MW')

        plt.subplots_adjust(left=0.12, bottom=0.1, right=0.96, top=0.96, wspace=None, hspace=0.6)

        plt.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)


class BatteryGraphicItem(QGraphicsItemGroup):

    def __init__(self, parent, api_obj, diagramScene):
        """

        :param parent:
        :param api_obj:
        """
        # QGraphicsPolygonItem.__init__(self, parent=parent)
        # QGraphicsItemGroup.__init__(self, parent=parent)
        super(BatteryGraphicItem, self).__init__(parent)

        self.parent = parent

        self.api_object = api_obj

        self.diagramScene = diagramScene

        self.w = 40
        self.h = 40

        # Properties of the container:
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        parent.scene().addItem(self.nexus)

        self.width = 2
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        pen = QPen(self.color, self.width, self.style)

        self.glyph = Square(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('B', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h/4, self.w/4)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w/2, pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + rect.height(),
        )

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pa = menu.addAction('Plot profiles')
        pa.triggered.connect(self.plot)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.diagramScene.removeItem(self.nexus)
        self.diagramScene.removeItem(self)
        self.api_object.bus.batteries.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object.active:
            self.set_enable(False)
        else:
            self.set_enable(True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)


    def plot(self):
        """
        Plot API objects profiles
        """
        fig = plt.figure(figsize=(10, 8))
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        self.api_object.Pprof.plot(ax=ax1, linewidth=1)
        self.api_object.Vsetprof.plot(ax=ax2, linewidth=1)

        ax1.set_title('Active power profile')
        ax2.set_title('Set voltage profile')

        ax1.set_ylabel('MW')
        ax2.set_ylabel('V (p.u.)')

        plt.subplots_adjust(left=0.12, bottom=0.1, right=0.96, top=0.96, wspace=None, hspace=0.6)

        plt.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers,
                           self.api_object.units,
                           self.api_object.edit_types,
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
        super(BusGraphicItem, self).__init__(parent)

        self.min_w = 60.0
        self.min_h = 60.0
        self.h = self.min_h
        self.w = self.min_w

        self.api_object = bus

        self.diagramScene = diagramScene  # this is the parent that hosts the pointer to the circuit

        self.editor = editor

        self.graphic_children = list()

        # Enabled for short circuit
        self.sc_enabled = False
        self.pen_width = 4
        # Properties of the rectangle:
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']
        self.setBrush(QBrush(Qt.darkGray))
        self.setPen(QPen(self.color, self.pen_width, self.style))
        self.setBrush(self.color)
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
        self.sizer.setPos(self.min_w, self.min_h)
        self.sizer.posChangeCallbacks.append(self.change_size)  # Connect the callback

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
        self.change_size(self.min_w, self.min_h)

    def change_size(self, w, h):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        if h < self.min_h:
            h = self.min_h
        if w < self.min_w:
            w = self.min_w

        self.setRect(0.0, 0.0, w, h)
        self.h = h
        self.w = w
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

        # rearrange children
        self.arrange_children()

        return w, h

    def arrange_children(self):
        """
        This function sorts the load and generators icons
        Returns:
            Nothing
        """
        y0 = self.h + 40
        x = 0
        for elm in self.graphic_children:
            elm.setPos(x, y0)
            x += elm.w + 10

    def create_children_icons(self):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """
        for elm in self.api_object.loads:
            self.add_load(elm)

        for elm in self.api_object.static_generators:
            self.add_static_generator(elm)

        for elm in self.api_object.controlled_generators:
            self.add_controlled_generator(elm)

        for elm in self.api_object.shunts:
            self.add_shunt(elm)

        for elm in self.api_object.batteries:
            self.add_battery(elm)

        self.arrange_children()

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

        menu.addSeparator()

        al = menu.addAction('Add load')
        al.triggered.connect(self.add_load)

        ash = menu.addAction('Add shunt')
        ash.triggered.connect(self.add_shunt)

        acg = menu.addAction('Add controlled generator')
        acg.triggered.connect(self.add_controlled_generator)

        asg = menu.addAction('Add static generator')
        asg.triggered.connect(self.add_static_generator)

        ab = menu.addAction('Add battery')
        ab.triggered.connect(self.add_battery)

        menu.addSeparator()

        arr = menu.addAction('Arrange')
        arr.triggered.connect(self.arrange_children)

        menu.addSeparator()

        sc = menu.addAction('Enable/Disable \nShort circuit')
        sc.triggered.connect(self.enable_disable_sc)

        menu.exec_(event.screenPos())

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.delete_all_connections()

        for g in self.graphic_children:
            self.diagramScene.removeItem(g.nexus)

        self.diagramScene.removeItem(self)
        self.diagramScene.circuit.delete_bus(self.api_object)

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        self.api_object.active = not self.api_object.active
        print('Enabled:', self.api_object.active)

        if self.api_object.active:

            self.setBrush(QBrush(ACTIVE['color']))

            for term in self.terminals:
                for host in term.hosting_connections:
                    host.set_enable(val=True)
        else:
            self.setBrush(QBrush(DEACTIVATED['color']))

            for term in self.terminals:
                for host in term.hosting_connections:
                    host.set_enable(val=False)

    def enable_disable_sc(self):
        """

        Returns:

        """
        if self.sc_enabled is True:
            self.setPen(QPen(QColor(ACTIVE['color']), self.pen_width))
            self.sc_enabled = False

        else:
            self.sc_enabled = True
            self.setPen(QPen(QColor(EMERGENCY['color']), self.pen_width))

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

        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=grid, editable=True, transposed=True)

        grid.setModel(mdl)
        dialogue.show()

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units, self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def add_load(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_load(self.api_object)

        _grph = LoadGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.graphic_children.append(_grph)
        self.arrange_children()

    def add_shunt(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_shunt(self.api_object)

        _grph = ShuntGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.graphic_children.append(_grph)
        self.arrange_children()

    def add_controlled_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_controlled_generator(self.api_object)

        _grph = ControlledGeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.graphic_children.append(_grph)
        self.arrange_children()

    def add_static_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_static_generator(self.api_object)

        _grph = StaticGeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.graphic_children.append(_grph)
        self.arrange_children()

    def add_battery(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_battery(self.api_object)

        _grph = BatteryGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.graphic_children.append(_grph)
        self.arrange_children()


class EditorGraphicsView(QGraphicsView):
    """
    Editor where the diagram is displayed
    """
    def __init__(self, scene, parent=None, editor=None):
        """

        @param scene: DiagramScene object
        @param parent:
        @param editor:
        """
        QGraphicsView.__init__(self, scene, parent)

        # self.setBackgroundBrush(QColor(0,66,255,180))
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setMouseTracking(True)
        self.setInteractive(True)
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

            # print(str(event.mimeData().data('component/name')))

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
                # print('Block created')

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
        # self.setBackgroundBrush(QtCore.Qt.red)

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


class GridEditor(QSplitter):

    def __init__(self, circuit: MultiCircuit):
        """
        Creates the Diagram Editor
        Args:
            circuit: Circuit that is handling
        """
        QSplitter.__init__(self)

        # store a reference to the multi circuit instance
        self.circuit = circuit

        # nodes distance "explosion" factor
        self.expand_factor = 1.5

        self.branch_editor_count = 1

        # Widget layout and child widgets:
        self.horizontalLayout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)
        self.libraryBrowserView = QListView(self)
        self.libraryModel = LibraryModel(self)
        self.libraryModel.setColumnCount(1)

        # Create an icon with an icon:
        object_factory = ObjectFactory()

        # initialize library of items
        self.libItems = list()
        self.libItems.append(QStandardItem(object_factory.get_box(), 'Bus'))
        for i in self.libItems:
            self.libraryModel.appendRow(i)

        # set the objects list
        self.object_types = ['Buses', 'Branches', 'Loads', 'Static Generators',
                             'Controlled Generators', 'Batteries', 'Shunts']

        # Actual libraryView object
        self.libraryBrowserView.setModel(self.libraryModel)
        self.libraryBrowserView.setViewMode(self.libraryBrowserView.ListMode)
        self.libraryBrowserView.setDragDropMode(self.libraryBrowserView.DragOnly)

        # create all the schematic objects and replace the existing ones
        self.diagramScene = DiagramScene(self, circuit)  # scene to add to the QGraphicsView
        self.diagramView = EditorGraphicsView(self.diagramScene, parent=self, editor=self)

        # create the grid name editor
        self.frame1 = QFrame()
        self.frame1_layout = QVBoxLayout()
        self.frame1_layout.setContentsMargins(0, 0, 0, 0)

        self.name_editor_frame = QFrame()
        self.name_layout = QHBoxLayout()
        self.name_layout.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLineEdit()
        self.name_label.setText(self.circuit.name)
        self.name_layout.addWidget(self.name_label)
        self.name_editor_frame.setLayout(self.name_layout)

        self.frame1_layout.addWidget(self.name_editor_frame)
        self.frame1_layout.addWidget(self.libraryBrowserView)
        self.frame1.setLayout(self.frame1_layout)

        # Add the two objects into a layout
        splitter2 = QSplitter(self)
        splitter2.addWidget(self.frame1)
        splitter2.addWidget(self.object_editor_table)
        splitter2.setOrientation(Qt.Vertical)
        self.addWidget(splitter2)
        self.addWidget(self.diagramView)
        splitter2.setStretchFactor(1, 6)

        self.startedConnection = None

        self.setStretchFactor(1, 10)

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

                        # if type(item.parent) is not type(self.startedConnection.fromPort.parent):
                        #  forbid same type connections

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

        # print('Buses:', len(self.circuit.buses))
        # print('Branches:', len(self.circuit.branches))

    def bigger_nodes(self):
        """
        Expand the grid
        @return:
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(self.diagramScene.selectedItems()) > 0:

            # expand selection
            for item in self.diagramScene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * self.expand_factor
                    y = item.pos().y() * self.expand_factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

        else:

            # expand all
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * self.expand_factor
                    y = item.pos().y() * self.expand_factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

        print('(', min_x, min_y, ')(', max_x, max_y, ')')

        h = max_y - min_y + 100
        w = max_x - min_x + 100
        self.diagramScene.setSceneRect(min_x, min_y, w, h)

    def smaller_nodes(self):
        """
        Contract the grid
        @return:
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(self.diagramScene.selectedItems()) > 0:

            # shrink selection only
            for item in self.diagramScene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() / self.expand_factor
                    y = item.pos().y() / self.expand_factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
        else:

            # shrink all
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() / self.expand_factor
                    y = item.pos().y() / self.expand_factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

        print('(', min_x, min_y, ')(', max_x, max_y, ')')

        h = max_y - min_y + 100
        w = max_x - min_x + 100
        self.diagramScene.setSceneRect(min_x, min_y, w, h)

    def center_nodes(self):
        """
        Center the view in the nodes
        @return: Nothing
        """
        self.diagramView.fitInView(self.diagramScene.sceneRect(), Qt.KeepAspectRatio)
        self.diagramView.scale(1.0, 1.0)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        if self.circuit.graph is None:
            self.circuit.compile()

        pos = nx.spectral_layout(self.circuit.graph, scale=2, weight='weight')

        pos = nx.fruchterman_reingold_layout(self.circuit.graph, dim=2, k=None, pos=pos, fixed=None, iterations=500,
                                             weight='weight', scale=20.0, center=None)

        # assign the positions to the graphical objects of the nodes
        for i, bus in enumerate(self.circuit.buses):
            try:
                x, y = pos[i] * 500
                bus.graphic_obj.setPos(QPoint(x, y))
            except KeyError as ex:
                warn('Node ' + str(i) + ' not in graph!!!! \n' + str(ex))

        self.center_nodes()

    def export(self, filename):
        """
        Save the grid to a png file
        :return:
        """

        image = QImage(1024, 768, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.diagramScene.render(painter)
        image.save(filename)
        painter.end()
