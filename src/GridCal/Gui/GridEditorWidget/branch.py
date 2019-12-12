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
import numpy as np

from GridCal.Gui.GridEditorWidget.generic import *
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Devices.branch import Branch, BranchType, TransformerType
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute


class TransformerEditor(QDialog):

    def __init__(self, branch: Branch, Sbase=100, modify_on_accept=True):
        """
        Transformer
        :param branch:
        :param Sbase:
        """
        super(TransformerEditor, self).__init__()

        # keep pointer to the line object
        self.branch = branch

        self.Sbase = Sbase

        self.modify_on_accept = modify_on_accept

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        self.Vf = self.branch.bus_from.Vnom
        self.Vt = self.branch.bus_to.Vnom

        R = self.branch.R
        X = self.branch.X
        G = self.branch.G
        B = self.branch.B
        Sn = self.branch.rate

        zsc = np.sqrt(R * R + X * X)
        Vsc = 100.0 * zsc
        Pcu = R * Sn * 1000.0

        if abs(G) > 0.0 and abs(B) > 0.0:
            zl = 1.0 / complex(G, B)
            rfe = zl.real
            xm = zl.imag

            Pfe = 1000.0 * Sn / rfe

            k = 1 / (rfe * rfe) + 1 / (xm * xm)
            I0 = 100.0 * np.sqrt(k)
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

    def get_template(self):
        """
        Fabricate template values from the branch values
        :return: TransformerType instance
        """
        eps = 1e-20
        Vf = self.branch.bus_from.Vnom  # kV
        Vt = self.branch.bus_to.Vnom  # kV
        Sn = self.sn_spinner.value() + eps  # MVA
        Pcu = self.pcu_spinner.value() + eps  # kW
        Pfe = self.pfe_spinner.value() + eps  # kW
        I0 = self.I0_spinner.value() + eps  # %
        Vsc = self.vsc_spinner.value()  # %

        Pfe = eps if Pfe == 0.0 else Pfe
        I0 = eps if I0 == 0.0 else I0

        tpe = TransformerType(hv_nominal_voltage=Vf,
                              lv_nominal_voltage=Vt,
                              nominal_power=Sn,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5)

        return tpe

    def accept_click(self):
        """
        Create transformer type and get the impedances
        :return:
        """

        if self.modify_on_accept:
            tpe = self.get_template()
            self.branch.apply_template(tpe, Sbase=self.Sbase)

        self.accept()


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

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

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

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1.0 / Zbase

        self.branch.R = np.round(R / Zbase, 6)
        self.branch.X = np.round(X / Zbase, 6)
        self.branch.G = np.round(G / Ybase, 6)
        self.branch.B = np.round(B / Ybase, 6)
        self.branch.rate = Sn

        self.accept()


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
        self.symbol_type = BranchType.Line
        self.symbol = None
        self.c0 = None
        self.c1 = None
        self.c2 = None
        if self.api_object is not None:
            self.update_symbol()

        # add the line and it possible children to the scene
        self.diagramScene.addItem(self)

        if fromPort and toPort:
            self.redraw()

    def remove_symbol(self):
        """
        Remove all symbols
        """
        for elm in [self.symbol, self.c1, self.c2, self.c0]:
            if elm is not None:
                try:
                    self.diagramScene.removeItem(elm)
                    # sip.delete(elm)
                    elm = None
                except:
                    pass

    def update_symbol(self):
        """
        Make the branch symbol
        :return:
        """

        # remove the symbol of the branch
        self.remove_symbol()

        if self.api_object.branch_type == BranchType.Transformer:
            self.make_transformer_symbol()
            self.symbol_type = BranchType.Transformer

        elif self.api_object.branch_type == BranchType.Switch:
            self.make_switch_symbol()
            self.symbol_type = BranchType.Switch

        elif self.api_object.branch_type == BranchType.Reactance:
            self.make_reactance_symbol()
            self.symbol_type = BranchType.Switch

        elif self.api_object.branch_type == BranchType.DCLine:
            self.make_dc_line_symbol()
            self.symbol_type = BranchType.DCLine

        else:
            # this is a line
            self.symbol = None
            self.c0 = None
            self.c1 = None
            self.c2 = None
            self.symbol_type = BranchType.Line

    def make_transformer_symbol(self):
        """
        create the transformer simbol
        :return:
        """
        h = 80.0
        w = h
        d = w/2
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(Qt.transparent))

        self.c0 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)
        self.c1 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)
        self.c2 = QGraphicsEllipseItem(0, 0, d, d, parent=self.symbol)

        self.c0.setPen(QPen(Qt.transparent, self.width, self.style))
        self.c2.setPen(QPen(self.color, self.width, self.style))
        self.c1.setPen(QPen(self.color, self.width, self.style))

        self.c0.setBrush(QBrush(Qt.white))
        self.c2.setBrush(QBrush(Qt.white))

        self.c0.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c1.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c2.setPos(w * 0.65 - d / 2, h * 0.5 - d / 2)

        self.c0.setZValue(0)
        self.c1.setZValue(2)
        self.c2.setZValue(1)

    def make_switch_symbol(self):
        """
        Mathe the switch symbol
        :return:
        """
        h = 40.0
        w = h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(self.color, self.width, self.style))
        if self.api_object.active:
            self.symbol.setBrush(self.color)
        else:
            self.symbol.setBrush(QBrush(Qt.white))

    def make_dc_line_symbol(self):
        """
        Make the DC Line symbol
        :return:
        """
        h = 30.0
        w = h
        w2 = int(w / 2)
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)

        offset = 3
        t_points = QPolygonF()
        t_points.append(QPointF(0, offset))
        t_points.append(QPointF(w-offset, w2))
        t_points.append(QPointF(0, w-offset))
        triangle = QGraphicsPolygonItem(self.symbol)
        triangle.setPolygon(t_points)
        triangle.setPen(QPen(Qt.white))
        triangle.setBrush(QBrush(Qt.white))

        line = QGraphicsRectItem(QRectF(h-offset, offset, offset, w-2*offset), parent=self.symbol)
        line.setPen(QPen(Qt.white))
        line.setBrush(QBrush(Qt.white))

        self.symbol.setPen(QPen(self.color, self.width, self.style))
        if self.api_object.active:
            self.symbol.setBrush(self.color)
        else:
            self.symbol.setBrush(QBrush(Qt.white))

    def make_reactance_symbol(self):
        """
        Make the reactance symbol
        :return:
        """
        h = 40.0
        w = 2 * h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(self.color, self.width, self.style))
        self.symbol.setBrush(self.color)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

        if self.symbol is not None:
            self.symbol.setToolTip(toolTip)

        if self.c0 is not None:
            self.c0.setToolTip(toolTip)
            self.c1.setToolTip(toolTip)
            self.c2.setToolTip(toolTip)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()

            pe = menu.addAction('Enable/Disable')
            pe.triggered.connect(self.enable_disable_toggle)

            menu.addSeparator()

            ra2 = menu.addAction('Delete')
            ra2.triggered.connect(self.remove)

            menu.addSeparator()

            ra3 = menu.addAction('Edit')
            ra3.triggered.connect(self.edit)

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            ra6.triggered.connect(self.plot_profiles)

            if self.api_object.branch_type == BranchType.Transformer:

                ra3 = menu.addAction('Add to catalogue')
                ra3.triggered.connect(self.add_to_templates)

                menu.addSeparator()

                ra4 = menu.addAction('Tap up')
                ra4.triggered.connect(self.tap_up)

                ra5 = menu.addAction('Tap down')
                ra5.triggered.connect(self.tap_down)

            menu.addSeparator()

            re = menu.addAction('Reduce')
            re.triggered.connect(self.reduce)

            menu.exec_(event.screenPos())
        else:
            pass

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """

        mdl = BranchObjectModel([self.api_object], self.api_object.editable_headers,
                                parent=self.diagramScene.parent().object_editor_table,
                                editable=True, transposed=True,
                                non_editable_attributes=self.api_object.non_editable_attributes)

        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """

        if self.api_object.branch_type in [BranchType.Transformer, BranchType.Line]:
            # trigger the editor
            self.edit()
        elif self.api_object.branch_type is BranchType.Switch:
            # change state
            self.enable_disable_toggle()

    def remove(self):
        """
        Remove this object in the diagram and the API
        @return:
        """
        self.diagramScene.circuit.delete_branch(self.api_object)
        self.diagramScene.removeItem(self)

    def reduce(self):
        """
        Reduce this branch
        """

        # get the index of the branch
        br_idx = self.diagramScene.circuit.branches.index(self.api_object)

        # call the reduction routine
        removed_branch, removed_bus, \
            updated_bus, updated_branches = reduce_grid_brute(self.diagramScene.circuit, br_idx)

        # remove the reduced branch
        removed_branch.graphic_obj.remove_symbol()
        self.diagramScene.removeItem(removed_branch.graphic_obj)

        # update the buses (the deleted one and the updated one)
        if removed_bus is not None:
            # merge the removed bus with the remaining one
            updated_bus.graphic_obj.merge(removed_bus.graphic_obj)

            # remove the updated bus children
            for g in updated_bus.graphic_obj.shunt_children:
                self.diagramScene.removeItem(g.nexus)
                self.diagramScene.removeItem(g)
            # re-draw the children
            updated_bus.graphic_obj.create_children_icons()

            # remove bus
            for g in removed_bus.graphic_obj.shunt_children:
                self.diagramScene.removeItem(g.nexus)  # remove the links between the bus and the children
            self.diagramScene.removeItem(removed_bus.graphic_obj)  # remove the bus and all the children contained

            #
            # updated_bus.graphic_obj.update()

        for br in updated_branches:
            # remove the branch from the schematic
            self.diagramScene.removeItem(br.graphic_obj)
            # add the branch to the schematic with the rerouting and all
            self.diagramScene.parent_.add_branch(br)
            # update both buses
            br.bus_from.graphic_obj.update()
            br.bus_to.graphic_obj.update()

    def remove_widget(self):
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

        # Switch coloring
        if self.symbol_type == BranchType.Switch:
            if self.api_object.active:
                self.symbol.setBrush(self.color)
            else:
                self.symbol.setBrush(Qt.white)

        if self.symbol_type == BranchType.DCLine:
            self.symbol.setBrush(self.color)
            if self.api_object.active:
                self.symbol.setPen(QPen(ACTIVE['color']))
            else:
                self.symbol.setPen(QPen(DEACTIVATED['color']))

        # Set pen for everyone
        self.set_pen(QPen(self.color, self.width, self.style))

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        # Ridiculously large call to get the main GUI that hosts this bus graphic
        # time series object from the last simulation
        ts = self.diagramScene.parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().time_series

        # get the index of this object
        i = self.diagramScene.circuit.branches.index(self.api_object)

        # plot the profiles
        self.api_object.plot_profiles(time_series=ts, my_index=i)

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

                # if the object branch type is different from the current displayed type, change it
                if self.symbol_type != self.api_object.branch_type:
                    self.update_symbol()

                if self.api_object.branch_type == BranchType.Line:
                    pass

                elif self.api_object.branch_type == BranchType.Branch:
                    pass

                else:

                    # if the branch has a moveable symbol, move it
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

        # Color the symbol only for switches
        if self.api_object.branch_type == BranchType.Switch:
            if self.symbol is not None:
                self.symbol.setPen(pen)

        elif self.api_object.branch_type == BranchType.Transformer:
            if self.c1 is not None:
                self.c1.setPen(pen)
                self.c2.setPen(pen)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        if self.api_object.branch_type == BranchType.Transformer:
            dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=True)
            if dlg.exec_():
                pass

        elif self.api_object.branch_type == BranchType.Line:
            dlg = LineEditor(self.api_object, Sbase)
            if dlg.exec_():
                pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        if self.api_object.branch_type == BranchType.Transformer:

            if self.api_object.template is not None:
                # automatically pick the template
                if isinstance(self.api_object.template, TransformerType):
                    self.diagramScene.circuit.add_transformer_type(self.api_object.template)
                else:
                    # raise dialogue to set the template
                    dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
                    if dlg.exec_():
                        tpe = dlg.get_template()
                        self.diagramScene.circuit.add_transformer_type(tpe)
            else:
                # raise dialogue to set the template
                dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
                if dlg.exec_():
                    tpe = dlg.get_template()
                    self.diagramScene.circuit.add_transformer_type(tpe)

        elif self.api_object.branch_type == BranchType.Line:
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

