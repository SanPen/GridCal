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

from GridCal.Gui.GuiFunctions import get_list_model
from GridCal.Gui.GridEditorWidget.generic_graphics import *
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.GridEditorWidget.messages import *
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Devices.line import Line, SequenceLineType, Tower, UndergroundLineType
from GridCal.Engine.Devices.dc_line import DcLine
from GridCal.Engine.Devices.branch import BranchType
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute


class DcLineEditor(QDialog):

    def __init__(self, branch: DcLine, Sbase=100, templates=None, current_template=None):
        """
        Line Editor constructor
        :param branch: Branch object to update
        :param Sbase: Base power in MVA
        """
        super(DcLineEditor, self).__init__()

        # keep pointer to the line object
        self.branch = branch

        self.Sbase = Sbase

        self.templates = templates

        self.current_template = current_template

        self.selected_template = None

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
        B = self.branch.B * Ybase

        I = self.branch.rate / Vf  # current in kA

        # ------------------------------------------------------------------------------------------

        # catalogue
        self.catalogue_combo = QComboBox()
        if self.templates is not None:
            if len(self.templates) > 0:
                self.catalogue_combo.setModel(get_list_model(self.templates))

                if self.current_template is not None:
                    try:
                        idx = self.templates.index(self.current_template)
                        self.catalogue_combo.setCurrentIndex(idx)

                        if isinstance(self.current_template, SequenceLineType):
                            I = self.current_template.rating
                            R = self.current_template.R

                        if isinstance(self.current_template, UndergroundLineType):
                            I = self.current_template.rating
                            R = self.current_template.R

                        elif isinstance(self.current_template, Tower):
                            I = self.current_template.rating
                            R = self.current_template.R1

                    except:
                        pass

        # load template
        self.load_template_btn = QPushButton()
        self.load_template_btn.setText('Load template values')
        self.load_template_btn.clicked.connect(self.load_template_btn_click)

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

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        if templates is not None:
            self.layout.addWidget(QLabel("Available templates"))
            self.layout.addWidget(self.catalogue_combo)
            self.layout.addWidget(self.load_template_btn)
            self.layout.addWidget(QLabel(""))

        self.layout.addWidget(QLabel("L: Line length [Km]"))
        self.layout.addWidget(self.l_spinner)

        self.layout.addWidget(QLabel("Imax: Max. current [KA] @" + str(int(Vf)) + " [KV]"))
        self.layout.addWidget(self.i_spinner)

        self.layout.addWidget(QLabel("R: Resistance [Ohm/Km]"))
        self.layout.addWidget(self.r_spinner)

        self.layout.addWidget(QLabel("X: Inductance [Ohm/Km]"))
        self.layout.addWidget(self.x_spinner)

        # self.layout.addWidget(QLabel("G: Conductance [S/Km]"))
        # self.layout.addWidget(self.g_spinner)

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

        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        Sn = np.round(I * Vf, 2)  # nominal power in MVA = kA * kV

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1.0 / Zbase

        self.branch.R = np.round(R / Zbase, 6)
        self.branch.rate = Sn

        if self.selected_template is not None:
            self.branch.template = self.selected_template

        self.accept()

    def load_template(self, template):
        """

        :param template:
        :return:
        """
        if isinstance(template, SequenceLineType):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R)

            self.selected_template = template

        elif isinstance(template, UndergroundLineType):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R)

            self.selected_template = template

        elif isinstance(template, Tower):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R1)

            self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:

            idx = self.catalogue_combo.currentIndex()
            template = self.templates[idx]

            self.load_template(template)


class DcLineGraphicItem(QGraphicsLineItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem, diagramScene, width=5, branch: DcLine = None):
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

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Line")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            ra3 = menu.addAction('Editor')
            edit_icon = QIcon()
            edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            ra3.setIcon(edit_icon)
            ra3.triggered.connect(self.edit)

            # menu.addSeparator()

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

            # menu.addSeparator()

            re = menu.addAction('Reduce')
            re_icon = QIcon()
            re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
            re.setIcon(re_icon)
            re.triggered.connect(self.reduce)

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

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
        ok = yes_no_question('Do you want to remove this line?', 'Remove line')

        if ok:
            self.diagramScene.circuit.delete_branch(self.api_object)
            self.diagramScene.removeItem(self)

    def reduce(self):
        """
        Reduce this branch
        """

        ok = yes_no_question('Do you want to reduce this line?', 'Reduce line')

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

                #
                # updated_bus.graphic_obj.update()

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

    def set_pen(self, pen):
        """
        Set pen to all objects
        Args:
            pen:
        """
        self.setPen(pen)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase
        templates = self.diagramScene.circuit.underground_cable_types + self.diagramScene.circuit.overhead_line_types
        current_template = self.api_object.template
        dlg = DcLineEditor(self.api_object, Sbase, templates, current_template)
        if dlg.exec_():
            pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        dlg = DcLineEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass


