import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import smopy
from PIL.ImageQt import ImageQt, Image
from GridCal.Engine.CalculationEngine import *
from GridCal.Gui.GuiFunctions import *


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
FONT_SCALE = 1.9


class LineEditor(QDialog):

    def __init__(self, branch: Branch, Sbase=100):
        """
        Line Editor constructor
        :param branch: Branch object to update
        :param Sbase: Base power in MVA
        """
        super(LineEditor, self).__init__()

        # keep pointer to the line object
        self.branch = branch

        self.Sbase = Sbase

        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        # assert (Vf == Vt)

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1 / Zbase

        R = self.branch.R * Zbase
        X = self.branch.X * Zbase
        G = self.branch.G * Ybase
        B = self.branch.B * Ybase

        I = self.branch.rate / Vf  # current in kA

        # ------------------------------------------------------------------------------------------

        # line length
        self.l_spinner = QDoubleSpinBox()
        self.l_spinner.setMinimum(0)
        self.l_spinner.setMaximum(9999999)
        self.l_spinner.setDecimals(6)
        self.l_spinner.setValue(1)

        # Max current
        self.i_spinner = QDoubleSpinBox()
        self.i_spinner.setMinimum(0)
        self.i_spinner.setMaximum(9999999)
        self.i_spinner.setDecimals(2)
        self.i_spinner.setValue(I)

        # R
        self.r_spinner = QDoubleSpinBox()
        self.r_spinner.setMinimum(0)
        self.r_spinner.setMaximum(9999999)
        self.r_spinner.setDecimals(6)
        self.r_spinner.setValue(R)

        # X
        self.x_spinner = QDoubleSpinBox()
        self.x_spinner.setMinimum(0)
        self.x_spinner.setMaximum(9999999)
        self.x_spinner.setDecimals(6)
        self.x_spinner.setValue(X)

        # G
        self.g_spinner = QDoubleSpinBox()
        self.g_spinner.setMinimum(0)
        self.g_spinner.setMaximum(9999999)
        self.g_spinner.setDecimals(6)
        self.g_spinner.setValue(G)

        # B
        self.b_spinner = QDoubleSpinBox()
        self.b_spinner.setMinimum(0)
        self.b_spinner.setMaximum(9999999)
        self.b_spinner.setDecimals(6)
        self.b_spinner.setValue(B)

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI
        self.layout.addWidget(QLabel("L: Line length [Km]"))
        self.layout.addWidget(self.l_spinner)

        self.layout.addWidget(QLabel("Imax: Max. current [KA] @" + str(int(Vf)) + " [KV]"))
        self.layout.addWidget(self.i_spinner)

        self.layout.addWidget(QLabel("R: Resistance [Ohm/Km]"))
        self.layout.addWidget(self.r_spinner)

        self.layout.addWidget(QLabel("X: Inductance [Ohm/Km]"))
        self.layout.addWidget(self.x_spinner)

        self.layout.addWidget(QLabel("G: Conductance [S/Km]"))
        self.layout.addWidget(self.g_spinner)

        self.layout.addWidget(QLabel("B: Susceptance [S/Km]"))
        self.layout.addWidget(self.b_spinner)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Line editor')

    def accept_click(self):
        """
        Set the values
        :return:
        """
        l = self.l_spinner.value()
        I = self.i_spinner.value()
        R = self.r_spinner.value() * l
        X = self.x_spinner.value() * l
        G = self.g_spinner.value() * l
        B = self.b_spinner.value() * l

        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        Sn = np.round(I * Vf, 2)  # nominal power in MVA = kA * kV

        # assert (Vf == Vt)

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1.0 / Zbase

        self.branch.R = np.round(R / Zbase, 6)
        self.branch.X = np.round(X / Zbase, 6)
        self.branch.G = np.round(G / Ybase, 6)
        self.branch.B = np.round(B / Ybase, 6)
        self.branch.rate = Sn

        self.accept()


class TransformerEditor(QDialog):

    def __init__(self, branch: Branch, Sbase=100):
        """
        Transformer
        :param branch:
        :param Sbase:
        """
        super(TransformerEditor, self).__init__()

        # keep pointer to the line object
        self.branch = branch

        self.Sbase = Sbase

        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        # assert (Vf == Vt)

        R = self.branch.R
        X = self.branch.X
        G = self.branch.G
        B = self.branch.B
        Sn = self.branch.rate

        zsc = sqrt(R * R + 1 / (X * X))
        Vsc = 100.0 * zsc
        Pcu = R * Sn * 1000.0

        if abs(G) > 0.0 and abs(B) > 0.0:
            zl = 1.0 / complex(G, B)
            rfe = zl.real
            xm = zl.imag

            Pfe = 1000.0 * Sn / rfe

            k = 1 / (rfe * rfe) + 1 / (xm * xm)
            I0 = 100.0 * sqrt(k)
        else:
            Pfe = 0
            I0 = 0

        # ------------------------------------------------------------------------------------------

        # Sn
        self.sn_spinner = QDoubleSpinBox()
        self.sn_spinner.setMinimum(0)
        self.sn_spinner.setMaximum(9999999)
        self.sn_spinner.setDecimals(6)
        self.sn_spinner.setValue(Sn)

        # Pcu
        self.pcu_spinner = QDoubleSpinBox()
        self.pcu_spinner.setMinimum(0)
        self.pcu_spinner.setMaximum(9999999)
        self.pcu_spinner.setDecimals(6)
        self.pcu_spinner.setValue(Pcu)

        # Pfe
        self.pfe_spinner = QDoubleSpinBox()
        self.pfe_spinner.setMinimum(0)
        self.pfe_spinner.setMaximum(9999999)
        self.pfe_spinner.setDecimals(6)
        self.pfe_spinner.setValue(Pfe)

        # I0
        self.I0_spinner = QDoubleSpinBox()
        self.I0_spinner.setMinimum(0)
        self.I0_spinner.setMaximum(9999999)
        self.I0_spinner.setDecimals(6)
        self.I0_spinner.setValue(I0)

        # Vsc
        self.vsc_spinner = QDoubleSpinBox()
        self.vsc_spinner.setMinimum(0)
        self.vsc_spinner.setMaximum(9999999)
        self.vsc_spinner.setDecimals(6)
        self.vsc_spinner.setValue(Vsc)

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI
        self.layout.addWidget(QLabel("Sn: Nominal power [MVA]"))
        self.layout.addWidget(self.sn_spinner)

        self.layout.addWidget(QLabel("Pcu: Copper losses [kW]"))
        self.layout.addWidget(self.pcu_spinner)

        self.layout.addWidget(QLabel("Pfe: Iron losses [kW]"))
        self.layout.addWidget(self.pfe_spinner)

        self.layout.addWidget(QLabel("I0: No load current [%]"))
        self.layout.addWidget(self.I0_spinner)

        self.layout.addWidget(QLabel("Vsc: Short circuit voltage [%]"))
        self.layout.addWidget(self.vsc_spinner)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Transformer editor')

    def accept_click(self):
        """
        Create transformer type and get the impedances
        :return:
        """

        Vf = self.branch.bus_from.Vnom  # kV
        Vt = self.branch.bus_to.Vnom  # kV
        Sn = self.sn_spinner.value()  # MVA
        Pcu = self.pcu_spinner.value()  # kW
        Pfe = self.pfe_spinner.value()  # kW
        I0 = self.I0_spinner.value()  # %
        Vsc = self.vsc_spinner.value()  # %

        eps = 1e-20

        # Vsc = eps if Vsc == 0.0 else Vsc
        # Pcu = eps if Pcu == 0.0 else Pcu
        Pfe = eps if Pfe == 0.0 else Pfe
        I0 = eps if I0 == 0.0 else I0

        tpe = TransformerType(HV_nominal_voltage=Vf,
                              LV_nominal_voltage=Vt,
                              Nominal_power=Sn,
                              Copper_losses=Pcu,
                              Iron_losses=Pfe,
                              No_load_current=I0,
                              Short_circuit_voltage=Vsc,
                              GR_hv1=0.5,
                              GX_hv1=0.5)

        leakage_impedance, magnetizing_impedance = tpe.get_impedances()

        # z_series = leakage_impedance
        # y_shunt = 1 / magnetizing_impedance

        self.branch.apply_transformer_type(tpe)

        self.accept()


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

        # ra1 = menu.addAction('Rotate +90')
        # ra1.triggered.connect(self.rotate_clockwise)
        # ra2 = menu.addAction('Rotate -90')
        # ra2.triggered.connect(self.rotate_counterclockwise)

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


class BranchGraphicItem(QGraphicsLineItem):

    def __init__(self, fromPort, toPort, diagramScene, width=5, branch: Branch = None):
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

        # add transformer circles
        self.symbol = None
        self.c0 = None
        self.c1 = None
        self.c2 = None
        if self.api_object is not None:
            if self.api_object.is_transformer:
                self.make_transformer_signs()

        # add the line and it possible children to the scene
        self.diagramScene.addItem(self)

        if fromPort and toPort:
            self.redraw()

    def make_transformer_signs(self):
        """
        create the transformer simbol
        :return:
        """
        h = 80.0
        w = h
        d = w/2
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(Qt.transparent)

        self.c0 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)
        self.c1 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)
        self.c2 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)

        self.c0.setPen(QPen(Qt.transparent, self.width, self.style))
        self.c2.setPen(QPen(self.color, self.width, self.style))
        self.c1.setPen(QPen(self.color, self.width, self.style))

        self.c0.setBrush(Qt.white)
        self.c2.setBrush(Qt.white)

        self.c0.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c1.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c2.setPos(w * 0.65 - d / 2, h * 0.5 - d / 2)

        self.c0.setZValue(0)
        self.c1.setZValue(2)
        self.c2.setZValue(1)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)
        if self.symbol is not None:
            self.symbol.setToolTip(toolTip)
            self.c0.setToolTip(toolTip)
            self.c1.setToolTip(toolTip)
            self.c2.setToolTip(toolTip)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        menu = QMenu()

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        menu.addSeparator()

        ra2 = menu.addAction('Delete')
        ra2.triggered.connect(self.remove)

        ra3 = menu.addAction('Edit')
        ra3.triggered.connect(self.edit)

        if self.api_object.is_transformer:
            ra4 = menu.addAction('Tap up')
            ra4.triggered.connect(self.tap_up)

            ra5 = menu.addAction('Tap down')
            ra5.triggered.connect(self.tap_down)

        menu.exec_(event.screenPos())

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True,
                           non_editable_indices=[1, 2])

        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """
        self.edit()

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
        if self.api_object is not None:
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
        self.set_pen(QPen(self.color, self.width, self.style))

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
            self.fromPort.parent.setZValue(0)

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
            self.toPort.parent.setZValue(0)

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

            # Set position
            self.setLine(QLineF(self.pos1, self.pos2))

            # set Z-Order (to the back)
            self.setZValue(-1)

            if self.api_object is not None:
                if self.api_object.is_transformer:

                    if self.c1 is None:
                        self.make_transformer_signs()

                    try:
                        h = self.pos2.y() - self.pos1.y()
                        b = self.pos2.x() - self.pos1.x()
                        ang = np.arctan2(h, b)
                        h2 = self.symbol.rect().height() / 2.0
                        w2 = self.symbol.rect().width() / 2.0
                        a = h2 * np.cos(ang) - w2 * np.sin(ang)
                        b = w2 * np.sin(ang) + h2 * np.cos(ang)

                        center = (self.pos1 + self.pos2) * 0.5 - QPointF(a, b)

                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(np.rad2deg(ang))
                        self.symbol.setTransform(transform)

                    except Exception as ex:
                        print(ex)

    def set_pen(self, pen):
        """
        Set pen to all objects
        Args:
            pen:
        """
        self.setPen(pen)
        if self.api_object.is_transformer:
            if self.c1 is None:
                self.redraw()
            self.c1.setPen(pen)
            self.c2.setPen(pen)

    def edit(self):
        """
        Open the apropiate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase
        if self.api_object.is_transformer:
            dlg = TransformerEditor(self.api_object, Sbase)
        else:
            dlg = LineEditor(self.api_object, Sbase)

        if dlg.exec_():
            pass

    def tap_up(self):
        """
        Set one tap up
        """
        self.api_object.tap_up()

    def tap_down(self):
        """
        Set one tap down
        """
        self.api_object.tap_down()


class ParameterDialog(QDialog):

    def __init__(self, parent=None):
        super(ParameterDialog, self).__init__(parent)
        self.button = QPushButton('Ok', self)
        l = QVBoxLayout(self)
        l.addWidget(self.button)
        self.button.clicked.connect(self.OK)

    def OK(self):
        self.close()


class TerminalItem(QGraphicsRectItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self, name, editor=None, parent=None, h=10, w=10):
        """

        @param name:
        @param editor:
        @param parent:
        """

        QGraphicsRectItem.__init__(self, QRectF(-6, -6, h, w), parent)
        self.setCursor(QCursor(QtCore.Qt.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        # terminal parent object
        self.parent = parent

        self.hosting_connections = list()

        self.editor = editor

        # Name:
        self.name = name
        self.posCallbacks = list()
        self.setFlag(self.ItemSendsScenePositionChanges, True)

    def process_callbacks(self, value):

        w = self.rect().width()
        h2 = self.rect().height() / 2.0
        n = len(self.posCallbacks)
        dx = w / (n + 1)
        for i, call_back in enumerate(self.posCallbacks):
            call_back(value + QPointF((i + 1) * dx, h2))

    def itemChange(self, change, value):
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == self.ItemScenePositionHasChanged:

            self.process_callbacks(value)
            # w = self.rect().width()
            # h2 = self.rect().height() / 2.0
            # n = len(self.posCallbacks)
            # dx = w / (n+1)
            # for i, call_back in enumerate(self.posCallbacks):
            #     call_back(value + QPointF((i+1) * dx, h2))

            return value

        else:
            return super(TerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Start a connection
        Args:
            event:

        Returns:

        """
        self.editor.startConnection(self)
        self.hosting_connections.append(self.editor.started_branch)

    def remove_all_connections(self):
        """
        Removes all the terminal connections
        Returns:

        """
        n = len(self.hosting_connections)
        for i in range(n - 1, -1, -1):
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

        self.width = 4

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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        # triangle
        self.glyph = Polygon(self)
        self.glyph.setPolygon(QPolygonF([QPointF(0, 0), QPointF(self.w, 0), QPointF(self.w / 2, self.h)]))
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.addToGroup(self.glyph)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y() + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

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
        if self.api_object is not None:
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
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
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

        self.width = 4

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
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        self.lines = list()
        self.lines.append(QLineF(QPointF(self.w / 2, 0), QPointF(self.w / 2, self.h * 0.4)))
        self.lines.append(QLineF(QPointF(0, self.h * 0.4), QPointF(self.w, self.h * 0.4)))
        self.lines.append(QLineF(QPointF(0, self.h * 0.6), QPointF(self.w, self.h * 0.6)))
        self.lines.append(QLineF(QPointF(self.w / 2, self.h * 0.6), QPointF(self.w / 2, self.h)))
        self.lines.append(QLineF(QPointF(0, self.h * 1), QPointF(self.w, self.h * 1)))
        self.lines.append(QLineF(QPointF(self.w * 0.15, self.h * 1.1), QPointF(self.w * 0.85, self.h * 1.1)))
        self.lines.append(QLineF(QPointF(self.w * 0.3, self.h * 1.2), QPointF(self.w * 0.7, self.h * 1.2)))
        for l in self.lines:
            l1 = QLine(self)
            l1.setLine(l)
            l1.setPen(pen)
            self.addToGroup(l1)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y() + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

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
        if self.api_object is not None:
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
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
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

        self.width = 4
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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Circle(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('G', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y() + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

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
        if self.api_object is not None:
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
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
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

        # l1 = QGraphicsLineItem(QLineF(QPointF(self.w/2, 0), QPointF(self.w/2, -10)))
        # l1.setPen(pen)
        # self.addToGroup(l1)

        self.width = 4
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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Square(parent)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('S', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y() + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

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
        if self.api_object is not None:
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
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
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

        self.width = 4
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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        parent.scene().addItem(self.nexus)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Square(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('B', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y() + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

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
        if self.api_object is not None:
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
        ax1 = fig.add_subplot(411)
        ax2 = fig.add_subplot(412)
        ax3 = fig.add_subplot(413)
        ax4 = fig.add_subplot(414)

        self.api_object.Pprof.plot(ax=ax1, linewidth=1)
        self.api_object.Vsetprof.plot(ax=ax2, linewidth=1)
        self.api_object.power_array.plot(ax=ax3, linewidth=1)
        self.api_object.energy_array.plot(ax=ax4, linewidth=1)

        ax1.set_title('Active power profile')
        ax2.set_title('Set voltage profile')
        ax3.set_title('Controlled active power profile')
        ax4.set_title('Controlled energy profile')

        ax1.set_ylabel('MW')
        ax2.set_ylabel('V (p.u.)')
        ax3.set_ylabel('MW')
        ax4.set_ylabel('MWh')

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


class BusGraphicItem(QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, diagramScene, name='Untitled', parent=None, index=0, editor=None,
                 bus: Bus = None, pos: QPoint = None):
        """

        @param diagramScene:
        @param name:
        @param parent:
        @param index:
        @param editor:
        """
        super(BusGraphicItem, self).__init__(parent)

        self.min_w = 180.0
        self.min_h = 20.0
        self.offset = 10
        self.h = bus.h if bus.h >= self.min_h else self.min_h
        self.w = bus.w if bus.w >= self.min_w else self.min_w

        self.api_object = bus

        self.diagramScene = diagramScene  # this is the parent that hosts the pointer to the circuit

        self.editor = editor

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = False
        self.pen_width = 4

        # index
        self.index = index

        if pos is not None:
            self.setPos(pos)

        # color
        if self.api_object is not None:
            if self.api_object.active:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
            else:
                self.color = DEACTIVATED['color']
                self.style = DEACTIVATED['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        # Label:
        self.label = QGraphicsTextItem(bus.name, self)
        # self.label.setDefaultTextColor(QtCore.Qt.white)
        self.label.setDefaultTextColor(QtCore.Qt.black)
        self.label.setScale(FONT_SCALE)

        # square
        self.tile = QGraphicsRectItem(0, 0, self.min_h, self.min_h, self)
        self.tile.setOpacity(0.7)

        # connection terminals the block
        self.terminal = TerminalItem('s', parent=self, editor=self.editor)  # , h=self.h))
        self.terminal.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.hosting_connections = list()

        # Create corner for resize:
        self.sizer = HandleItem(self.terminal)
        self.sizer.setPos(self.w, self.h)
        self.sizer.posChangeCallbacks.append(self.change_size)  # Connect the callback
        self.sizer.setFlag(self.ItemIsMovable)
        self.adapt()

        # self.setBrush(QBrush(Qt.white))
        # self.setOpacity(0.4)
        # self.setPen(QPen(self.color, self.pen_width, self.style))
        # self.setBrush(self.color)

        self.set_tile_color(self.color)

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        # Update size:
        self.change_size(self.w, self.h)

    # def setPen(self, pen):
    #     self.tile.setPen(pen)
    #
    def set_tile_color(self, brush):
        self.tile.setBrush(brush)
        self.terminal.setBrush(brush)

    def change_size(self, w, h):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        # if h < self.min_h:
        #     h = self.min_h
        h = self.min_h
        if w < self.min_w:
            w = self.min_w

        self.setRect(0.0, 0.0, w, h)
        self.h = h
        self.w = w

        # center label:
        rect = self.label.boundingRect()
        lw, lh = rect.width(), rect.height()
        lx = (w - lw) / 2
        ly = (h - lh) / 2 - lh * (FONT_SCALE - 1)
        self.label.setPos(lx, ly)

        # lower
        y0 = h + self.offset
        x0 = 0
        self.terminal.setPos(x0, y0)
        self.terminal.setRect(0.0, 0.0, w, 10)

        # Set text
        if self.api_object is not None:
            self.label.setPlainText(self.api_object.name)

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
        n = len(self.shunt_children)
        inc_x = self.w / (n + 1)
        x = inc_x
        for elm in self.shunt_children:
            elm.setPos(x - elm.w / 2, y0)
            x += inc_x

        # Arrange line positions
        self.terminal.process_callbacks(self.pos() + self.terminal.pos())

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

        # ra1 = menu.addAction('Rotate +90')
        # ra1.triggered.connect(self.rotate_clockwise)
        # ra2 = menu.addAction('Rotate -90')
        # ra2.triggered.connect(self.rotate_counterclockwise)

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

    def delete_all_connections(self):

        self.terminal.remove_all_connections()

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.delete_all_connections()

        for g in self.shunt_children:
            self.diagramScene.removeItem(g.nexus)

        self.diagramScene.removeItem(self)
        self.diagramScene.circuit.delete_bus(self.api_object)

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        if self.api_object is not None:
            self.api_object.active = not self.api_object.active
            # print('Enabled:', self.api_object.active)

            if self.api_object.active:

                self.set_tile_color(QBrush(ACTIVE['color']))
                # self.setPen(QPen(ACTIVE['style']))
                # self.color = ACTIVE['color']
                # self.style = ACTIVE['style']

                for host in self.terminal.hosting_connections:
                    host.set_enable(val=True)
            else:
                self.set_tile_color(QBrush(DEACTIVATED['color']))
                # self.setPen(QPen(ACTIVE['style']))

                # self.color = DEACTIVATED['color']
                # self.style = DEACTIVATED['style']

                for host in self.terminal.hosting_connections:
                    host.set_enable(val=False)

    def enable_disable_sc(self):
        """

        Returns:

        """
        if self.sc_enabled is True:
            # self.tile.setPen(QPen(QColor(ACTIVE['color']), self.pen_width))
            self.tile.setPen(QPen(Qt.transparent, self.pen_width))
            self.sc_enabled = False

        else:
            self.sc_enabled = True
            self.tile.setPen(QPen(QColor(EMERGENCY['color']), self.pen_width))

    def plot_profiles(self):
        """

        @return:
        """
        # t = self.diagramScene.circuit.master_time_array
        # self.api_object.plot_profiles(time_idx=t)
        self.api_object.plot_profiles()

    def mousePressEvent(self, event):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object], self.api_object.edit_headers, self.api_object.units,
                           self.api_object.edit_types,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """
        Mouse double click
        :param event: event object
        """
        self.adapt()

    def adapt(self):
        """
        Set the bus width according to the label text
        """
        h = self.terminal.boundingRect().height()
        w = len(self.api_object.name) * 8 + 10
        self.change_size(w=w, h=h)
        self.sizer.setPos(w, self.h)

    def add_load(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_load(self.api_object)

        _grph = LoadGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_shunt(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_shunt(self.api_object)

        _grph = ShuntGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_controlled_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_controlled_generator(self.api_object)

        _grph = ControlledGeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_static_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_static_generator(self.api_object)

        _grph = StaticGeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_battery(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_battery(self.api_object)

        _grph = BatteryGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()


class MapWidget(QGraphicsRectItem):

    def __init__(self, scene: QGraphicsScene, view: QGraphicsView, lat0=42, lon0=55, zoom=3):
        super(MapWidget, self).__init__(None)

        self.scene = scene
        self.view = view

        # self.setRect(self.scene.sceneRect())
        # self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setFlags(self.ItemIsMovable)
        self.image = None
        self.img = None

        self.pen_width = 4
        # Properties of the rectangle:
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']
        self.setBrush(QBrush(Qt.darkGray))
        self.setPen(QPen(self.color, self.pen_width, self.style))
        self.setBrush(self.color)

        self.scene.addItem(self)

        self.h = view.size().height()
        self.w = view.size().width()

        self.lat0 = lat0
        self.lon0 = lon0
        self.zoom = zoom

        # Create corner for resize:
        self.sizer = HandleItem(self)
        self.sizer.setPos(self.w, self.h)
        self.sizer.posChangeCallbacks.append(self.change_size)  # Connect the callback
        # self.sizer.setFlag(self.sizer.ItemIsSelectable, True)

        self.change_size(self.w, self.h)
        self.setPos(0, self.h)

        # self.load_map()

    def change_size(self, w, h):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """

        self.setRect(0.0, 0.0, w, h)
        self.h = h
        self.w = w
        self.repaint()

        return w, h

    def load_map(self, lat0=42, lon0=55, zoom=3):
        """
        Load a map image into the widget
        :param lat0:
        :param lon0:
        :param zoom: 1~14
        """
        # store coordinates
        self.lat0 = lat0
        self.lon0 = lon0
        self.zoom = zoom

        print('map:', lat0, lon0, zoom)

        # get map
        try:
            map = smopy.Map((lat0, lon0), z=zoom)

            # w, h = map.img.size
            self.img = ImageQt(map.img)
            self.image = QPixmap.fromImage(self.img)
            self.image = self.image.scaled(QSize(self.w, self.h), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        except:
            warn('Could not load the map')

    def repaint(self):
        """
        Reload with the last parameters
        """
        self.load_map(self.lat0, self.lon0, self.zoom)

    def paint(self, painter, option, widget=None):
        """
        Action that happens on widget repaint
        :param painter:
        :param option:
        :param widget:
        """
        if self.image is not None:
            painter.drawPixmap(QPoint(0, 0), self.image)
            self.scene.update()


class EditorGraphicsView(QGraphicsView):

    def __init__(self, scene, parent=None, editor=None, lat0=42, lon0=55, zoom=3):
        """
        Editor where the diagram is displayed
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

        self.map = MapWidget(self.scene_, self, lat0, lon0, zoom)

    def adapt_map_size(self):
        w = self.size().width()
        h = self.size().height()
        print('EditorGraphicsView size: ', w, h)
        self.map.change_size(w, h)

    def view_map(self, flag=True):
        """

        :param flag:
        :return:
        """
        self.map.setVisible(flag)

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
            obj_type = event.mimeData().data('component/name')
            elm = None
            data = QByteArray()
            stream = QDataStream(data, QIODevice.WriteOnly)
            stream.writeQString('Bus')
            if obj_type == data:
                name = 'Bus ' + str(self.last_n)
                self.last_n += 1
                obj = Bus(name=name)
                elm = BusGraphicItem(diagramScene=self.scene(), name=name, editor=self.editor, bus=obj)
                obj.graphic_obj = elm
                self.scene_.circuit.add_bus(obj)  # weird but it's the only way to have graphical-API communication

            if elm is not None:
                elm.setPos(self.mapToScene(event.pos()))
                self.scene_.addItem(elm)

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
        """
        Add bus
        Args:
            bus: GridCal Bus object
            explode_factor: factor to position the node
        """
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
        Items model to host the draggable icons
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

    def __init__(self, parent=None, circuit: MultiCircuit = None):
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

    def __init__(self, circuit: MultiCircuit, lat0=42, lon0=55, zoom=3):
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
        self.diagramView = EditorGraphicsView(self.diagramScene, parent=self, editor=self,
                                              lat0=lat0, lon0=lon0, zoom=zoom)

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
        splitter2.setStretchFactor(1, 10)

        self.started_branch = None

        self.setStretchFactor(1, 10)

    def startConnection(self, port: TerminalItem):
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.started_branch = BranchGraphicItem(port, None, self.diagramScene)
        self.started_branch.bus_from = port.parent
        port.setZValue(0)
        # if self.diagramView.map.isVisible():
        #     self.diagramView.map.setZValue(-1)
        port.process_callbacks(port.parent.pos() + port.pos())

    def sceneMouseMoveEvent(self, event):
        """

        @param event:
        @return:
        """
        if self.started_branch:
            pos = event.scenePos()
            self.started_branch.setEndPos(pos)

    def sceneMouseReleaseEvent(self, event):
        """
        Finalize the branch creation if its drawing ends in a terminal
        @param event:
        @return:
        """
        # Clear or finnish the started connection:
        if self.started_branch:
            pos = event.scenePos()
            items = self.diagramScene.items(pos)  # get the item (the terminal) at the mouse position

            for item in items:
                if type(item) is TerminalItem:  # connect only to terminals
                    if item.parent is not self.started_branch.fromPort.parent:  # forbid connecting to itself

                        # if type(item.parent) is not type(self.startedConnection.fromPort.parent):
                        #  forbid same type connections

                        self.started_branch.setToPort(item)
                        item.hosting_connections.append(self.started_branch)
                        # self.started_branch.setZValue(-1)
                        self.started_branch.bus_to = item.parent
                        name = 'Branch ' + str(self.branch_editor_count)
                        v1 = self.started_branch.bus_from.api_object.Vnom
                        v2 = self.started_branch.bus_to.api_object.Vnom

                        if abs(v1 - v2) > 1.0:
                            is_transformer = True
                        else:
                            is_transformer = False

                        obj = Branch(bus_from=self.started_branch.bus_from.api_object,
                                     bus_to=self.started_branch.bus_to.api_object,
                                     name=name,
                                     is_transformer=is_transformer)
                        obj.graphic_obj = self.started_branch
                        self.started_branch.api_object = obj
                        self.circuit.add_branch(obj)
                        item.process_callbacks(item.parent.pos() + item.pos())

                        self.started_branch.setZValue(-1)
                        # if self.diagramView.map.isVisible():
                        #     self.diagramView.map.setZValue(-1)

            if self.started_branch.toPort is None:
                self.started_branch.remove_()

        # release this pointer
        self.started_branch = None

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

        # print('(', min_x, min_y, ')(', max_x, max_y, ')')

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

        # print('(', min_x, min_y, ')(', max_x, max_y, ')')

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

    def export(self, filename, w=1920, h=1080):
        """
        Save the grid to a png file
        :return:
        """

        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.diagramScene.render(painter)
        image.save(filename)
        painter.end()
