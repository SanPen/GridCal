# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np

from GridCal.Gui.GuiFunctions import get_list_model
from GridCal.Gui.GridEditorWidget.generic_graphics import *
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.GridEditorWidget.messages import *
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Devices.line import Line, SequenceLineType, Tower, UndergroundLineType
from GridCal.Engine.Devices.branch import BranchType
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute


class LineEditor(QDialog):

    def __init__(self, line: Line, Sbase=100, templates=None, current_template=None):
        """
        Line Editor constructor
        :param line: Branch object to update
        :param Sbase: Base power in MVA
        """
        super(LineEditor, self).__init__()

        # keep pointer to the line object
        self.line = line

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

        Vf = self.line.bus_from.Vnom
        Vt = self.line.bus_to.Vnom

        Zbase = (Vf * Vf) / self.Sbase
        Ybase = 1 / Zbase
        length = self.line.length

        if length == 0:
            length = 1.0

        R = self.line.R * Zbase / length
        X = self.line.X * Zbase / length
        B = self.line.B * Ybase / length
        I = np.round(self.line.rate / (Vf * 1.73205080757), 6)  # current in kA

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
                            X = self.current_template.X
                            B = self.current_template.B

                        if isinstance(self.current_template, UndergroundLineType):
                            I = self.current_template.rating
                            R = self.current_template.R
                            X = self.current_template.X
                            B = self.current_template.B

                        elif isinstance(self.current_template, Tower):
                            I = self.current_template.rating
                            R = self.current_template.R1
                            X = self.current_template.X1
                            B = self.current_template.Bsh1

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
        self.l_spinner.setValue(length)

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
        length = self.l_spinner.value()
        I = self.i_spinner.value()
        R = self.r_spinner.value() * length
        X = self.x_spinner.value() * length
        B = self.b_spinner.value() * length

        Vf = self.line.bus_from.Vnom
        Vt = self.line.bus_to.Vnom

        Zbase = (Vf * Vf) / self.Sbase
        Ybase = 1.0 / Zbase

        self.line.R = np.round(R / Zbase, 6)
        self.line.X = np.round(X / Zbase, 6)
        self.line.B = np.round(B / Ybase, 6)
        self.line.rate = np.round(I * Vf * 1.73205080757, 6)  # nominal power in MVA = kA * kV
        self.line.length = length

        if self.selected_template is not None:
            self.line.template = self.selected_template

        self.accept()

    def load_template(self, template):
        """

        :param template:
        :return:
        """
        if isinstance(template, SequenceLineType):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R)
            self.x_spinner.setValue(template.X)
            self.b_spinner.setValue(template.B)

            self.selected_template = template

        elif isinstance(template, UndergroundLineType):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R)
            self.x_spinner.setValue(template.X)
            self.b_spinner.setValue(template.B)

            self.selected_template = template

        elif isinstance(template, Tower):
            self.i_spinner.setValue(template.rating)
            self.r_spinner.setValue(template.R1)
            self.x_spinner.setValue(template.X1)
            self.b_spinner.setValue(template.Bsh1)

            self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:

            idx = self.catalogue_combo.currentIndex()
            template = self.templates[idx]

            self.load_template(template)


class LineGraphicItem(QGraphicsLineItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem, diagramScene, width=5, branch: Line = None):
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

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.setPen(QPen(color, w, style))

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

        if self.api_object.branch_type == BranchType.Switch:
            self.make_switch_symbol()
            self.symbol_type = BranchType.Switch

        elif self.api_object.branch_type == BranchType.Reactance:
            self.make_reactance_symbol()
            self.symbol_type = BranchType.Switch

        else:
            # this is a line
            self.symbol = None
            self.c0 = None
            self.c1 = None
            self.c2 = None
            self.symbol_type = BranchType.Line

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

            menu.addSection('Convert to')
            toxfo = menu.addAction('Transformer')
            toxfo_icon = QIcon()
            toxfo_icon.addPixmap(QPixmap(":/Icons/icons/to_transformer.svg"))
            toxfo.setIcon(toxfo_icon)
            toxfo.triggered.connect(self.to_transformer)

            tohvdc = menu.addAction('HVDC')
            tohvdc_icon = QIcon()
            tohvdc_icon.addPixmap(QPixmap(":/Icons/icons/to_hvdc.svg"))
            tohvdc.setIcon(tohvdc_icon)
            tohvdc.triggered.connect(self.to_hvdc)

            tovsc = menu.addAction('VSC')
            tovsc_icon = QIcon()
            tovsc_icon.addPixmap(QPixmap(":/Icons/icons/to_vsc.svg"))
            tovsc.setIcon(tovsc_icon)
            tovsc.triggered.connect(self.to_vsc)

            toupfc = menu.addAction('UPFC')
            toupfc_icon = QIcon()
            toupfc_icon.addPixmap(QPixmap(":/Icons/icons/to_upfc.svg"))
            toupfc.setIcon(toupfc_icon)
            toupfc.triggered.connect(self.to_upfc)

            menu.exec_(event.screenPos())
        else:
            pass

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        if self.api_object is not None:
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
        if self.api_object is not None:
            if self.api_object.branch_type in [BranchType.Transformer, BranchType.Line]:
                # trigger the editor
                self.edit()
            elif self.api_object.branch_type is BranchType.Switch:
                # change state
                self.enable_disable_toggle()

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            ok = yes_no_question('Do you want to remove this line?', 'Remove line')
        else:
            ok = True

        if ok:
            self.diagramScene.circuit.delete_line(self.api_object)
            self.diagramScene.removeItem(self)

    def reduce(self):
        """
        Reduce this branch
        """

        ok = yes_no_question('Do you want to reduce this line?', 'Reduce line')

        if ok:
            # get the index of the branch
            br_idx = self.diagramScene.circuit.lines.index(self.api_object)

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

            if self.diagramScene.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.diagramScene.set_active_status_to_profile(self.api_object, override_question=True)

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
        # get the index of this object
        i = self.diagramScene.circuit.get_branches().index(self.api_object)
        self.diagramScene.plot_branch(i, self.api_object)

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
        templates = self.diagramScene.circuit.underground_cable_types + self.diagramScene.circuit.overhead_line_types
        current_template = self.api_object.template
        dlg = LineEditor(self.api_object, Sbase, templates, current_template)
        if dlg.exec_():
            pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

        dlg = LineEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass

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

    def to_transformer(self):
        """
        Convert this object to transformer
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a transformer?', 'Convert line')
        if ok:
            editor = self.diagramScene.parent()
            editor.convert_line_to_transformer(self.api_object)

    def to_hvdc(self):
        """
        Convert this object to HVDC
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a HVDC line?', 'Convert line')
        if ok:
            editor = self.diagramScene.parent()
            editor.convert_line_to_hvdc(self.api_object)

    def to_vsc(self):
        """
        Convert this object to VSC
        :return:
        """
        if self.api_object.convertible_to_vsc():
            ok = yes_no_question('Are you sure that you want to convert this line into a VSC device?', 'Convert line')
            if ok:
                editor = self.diagramScene.parent()
                editor.convert_line_to_vsc(self.api_object)
        else:
            warning_msg('Unable to convert to VSC. One of the buses must be DC and the other AC.')

    def to_upfc(self):
        """
        Convert this object to UPFC
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a UPFC device?', 'Convert line')
        if ok:
            editor = self.diagramScene.parent()
            editor.convert_line_to_upfc(self.api_object)