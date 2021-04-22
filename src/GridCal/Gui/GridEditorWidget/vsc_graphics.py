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

from GridCal.Gui.GridEditorWidget.generic_graphics import *
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Devices.vsc import VSC
from GridCal.Engine.Devices.branch import Branch, BranchType
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute
from GridCal.Gui.GridEditorWidget.messages import *


class VscEditor(QDialog):

    def __init__(self, branch: VSC, Sbase=100):
        """
        Line Editor constructor
        :param branch: Branch object to update
        :param Sbase: Base power in MVA
        """
        super(VscEditor, self).__init__()

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


class VscGraphicItem(QGraphicsLineItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem, diagramScene, width=5, branch: VSC = None):
        """

        :param fromPort:
        :param toPort:
        :param diagramScene:
        :param width:
        :param branch:
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
        h = 48
        w = h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        if self.api_object is not None:
            self.update_symbol()

        # add the line and it possible children to the scene
        self.diagramScene.addItem(self)

        if fromPort and toPort:
            self.redraw()

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.setPen(QPen(color, w, style))
        self.symbol.setPen(QPen(color, w, style))
        self.symbol.setBrush(color)

    def remove_symbol(self):
        """
        Remove all symbols
        """
        for elm in [self.symbol]:
            if elm is not None:
                try:
                    self.diagramScene.removeItem(elm)
                except:
                    pass

    def update_symbol(self):
        """
        Make the branch symbol
        """

        # remove the symbol of the branch
        self.remove_symbol()
        self.make_vsc_symbol()

    def make_vsc_symbol(self):
        """
        Make the VSC symbol
        """
        h = 48
        w = h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(self.color, self.width, self.style))

        graphic = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self.symbol)
        graphic.setBrush(QBrush(QPixmap(":/Icons/icons/vsc.svg")))
        graphic.setPen(QPen(Qt.transparent, self.width, self.style))

        if self.api_object.active:
            self.symbol.setBrush(self.color)
        else:
            self.symbol.setBrush(QBrush(Qt.white))

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

        if self.symbol is not None:
            self.symbol.setToolTip(toolTip)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()

            pe = menu.addAction('Enable/Disable')
            pe_icon = QIcon()
            if self.api_object.active:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/uncheck_all.svg"))
            else:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/check_all.svg"))
            pe.setIcon(pe_icon)
            pe.triggered.connect(self.enable_disable_toggle)

            menu.addSeparator()

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            menu.addSeparator()

            ra3 = menu.addAction('Edit')
            edit_icon = QIcon()
            edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            ra3.setIcon(edit_icon)
            ra3.triggered.connect(self.edit)

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra4 = menu.addAction('Assign rate to profile')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.assign_rate_to_profile)

            ra5 = menu.addAction('Assign active state to profile')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.assign_status_to_profile)

            menu.addSeparator()

            re = menu.addAction('Reduce')
            re_icon = QIcon()
            re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
            re.setIcon(re_icon)
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
        ok = yes_no_question('Do you want to remove this VSC?', 'Remove VSC')

        if ok:
            self.diagramScene.circuit.delete_branch(self.api_object)
            self.diagramScene.removeItem(self)

    def reduce(self):
        """
        Reduce this branch
        """
        ok = yes_no_question('Do you want to reduce this VSC?', 'Remove VSC')

        if ok:
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

            for br in updated_branches:
                # remove the branch from the schematic
                self.diagramScene.removeItem(br.graphic_obj)
                # add the branch to the schematic with the rerouting and all
                self.diagramScene.parent_.add_line(br)
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
        if self.api_object.active:
            self.symbol.setBrush(self.color)
            self.symbol.setPen(QPen(ACTIVE['color']))
        else:
            self.symbol.setBrush(DEACTIVATED['color'])
            self.symbol.setPen(QPen(DEACTIVATED['color']))

        # Set pen for everyone
        self.set_pen(QPen(self.color, self.width, self.style))

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        i = self.diagramScene.circuit.get_branches().index(self.api_object)
        self.diagramScene.plot_branch(i, self.api_object)

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_active_status_to_profile(self.api_object)

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

        if self.symbol is not None:
            self.symbol.setPen(pen)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        dlg = VscEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        dlg = VscEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass
