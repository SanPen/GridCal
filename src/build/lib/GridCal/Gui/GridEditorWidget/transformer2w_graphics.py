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
from typing import List
from GridCal.Gui.GuiFunctions import get_list_model
from GridCal.Gui.GridEditorWidget.generic_graphics import *
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.GridEditorWidget.messages import *
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Devices.transformer import Transformer2W, TransformerType
from GridCal.Engine.Devices.branch import BranchType
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute


class TransformerEditor(QDialog):

    def __init__(self, branch: Transformer2W, Sbase=100, modify_on_accept=True, templates=None, current_template=None):
        """
        Transformer
        :param branch:
        :param Sbase:
        """
        super(TransformerEditor, self).__init__()

        # keep pointer to the line object
        self.transformer_obj = branch

        self.Sbase = Sbase

        self.modify_on_accept = modify_on_accept

        self.templates = self.filter_valid_templates(templates)

        self.current_template = current_template

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        self.Vf = self.transformer_obj.bus_from.Vnom
        self.Vt = self.transformer_obj.bus_to.Vnom

        # Change the impedances to the system base
        base_change = Sbase / (self.transformer_obj.rate + 1e-9)

        R = self.transformer_obj.R / base_change
        X = self.transformer_obj.X / base_change
        G = self.transformer_obj.G / base_change
        B = self.transformer_obj.B / base_change
        Sn = self.transformer_obj.rate

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

        # catalogue
        self.catalogue_combo = QComboBox()
        if templates is not None:
            if len(self.templates) > 0:

                self.catalogue_combo.setModel(get_list_model(self.templates))

                if self.current_template is not None:
                    try:
                        idx = self.templates.index(self.current_template)
                        self.catalogue_combo.setCurrentIndex(idx)

                        # set the template parameters
                        Sn = self.current_template.rating  # MVA
                        Pcu = self.current_template.Pcu  # kW
                        Pfe = self.current_template.Pfe  # kW
                        I0 = self.current_template.I0  # %
                        Vsc = self.current_template.Vsc  # %
                    except:
                        pass

        # load template
        self.load_template_btn = QPushButton()
        self.load_template_btn.setText('Load template values')
        self.load_template_btn.clicked.connect(self.load_template_btn_click)

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

        # add all to the GUI
        if templates is not None:
            self.layout.addWidget(QLabel("Suitable templates"))
            self.layout.addWidget(self.catalogue_combo)
            self.layout.addWidget(self.load_template_btn)
            self.layout.addWidget(QLabel(""))

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

        # self.layout.addWidget(self.system_base_chk)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Transformer editor')

    def filter_valid_templates(self, templates: List[TransformerType]):
        """
        Filter templates
        :param templates:
        :return:
        """
        if templates is None:
            return None

        lst = list()

        Vf = self.transformer_obj.bus_from.Vnom
        Vt = self.transformer_obj.bus_to.Vnom

        for tpe in templates:

            HV2 = tpe.HV * 1.01
            HV1 = tpe.HV * 0.99

            LV2 = tpe.LV * 1.01
            LV1 = tpe.LV * 0.99

            # check that the voltages are within a 1% tolerance
            if (HV1 < Vf < HV2) or (LV1 < Vf < LV2):
                if (HV1 < Vt < HV2) or (LV1 < Vt < LV2):
                    lst.append(tpe)

        return lst

    def get_template(self):
        """
        Fabricate template values from the branch values
        :return: TransformerType instance
        """
        eps = 1e-20
        Vf = self.transformer_obj.bus_from.Vnom  # kV
        Vt = self.transformer_obj.bus_to.Vnom  # kV
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

            if self.selected_template is None:
                # no selected template, but a new one was generated
                tpe = self.get_template()
            else:
                # pick the last selected template
                tpe = self.selected_template

            self.transformer_obj.apply_template(tpe, Sbase=self.Sbase)

        self.accept()

    def load_template(self, template: TransformerType):
        """

        :param template:
        :return:
        """
        self.sn_spinner.setValue(template.rating)  # MVA
        self.pcu_spinner.setValue(template.Pcu)  # kW
        self.pfe_spinner.setValue(template.Pfe)  # kW
        self.I0_spinner.setValue(template.I0)  # %
        self.vsc_spinner.setValue(template.Vsc)  # %

        self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:

            idx = self.catalogue_combo.currentIndex()
            template = self.templates[idx]

            if isinstance(template, TransformerType):
                self.load_template(template)


class TransformerGraphicItem(QGraphicsLineItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem, diagramScene, width=5,
                 branch: Transformer2W = None):
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
        self.c2.setPen(QPen(color, w, style))
        self.c1.setPen(QPen(color, w, style))

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
        self.make_transformer_symbol()
        self.symbol_type = BranchType.Transformer

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
            menu.addSection("Transformer")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            re = menu.addAction('Reduce')
            re_icon = QIcon()
            re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
            re.setIcon(re_icon)
            re.triggered.connect(self.reduce)

            ra3 = menu.addAction('Editor')
            edit_icon = QIcon()
            edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            ra3.setIcon(edit_icon)
            ra3.triggered.connect(self.edit)

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra3 = menu.addAction('Add to catalogue')
            ra3_icon = QIcon()
            ra3_icon.addPixmap(QPixmap(":/Icons/icons/Catalogue.svg"))
            ra3.setIcon(ra3_icon)
            ra3.triggered.connect(self.add_to_templates)

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

            ra7 = menu.addAction('Flip')
            ra7_icon = QIcon()
            ra7_icon.addPixmap(QPixmap(":/Icons/icons/redo.svg"))
            ra7.setIcon(ra7_icon)
            ra7.triggered.connect(self.flip_connections)

            menu.addSection('Tap changer')

            ra4 = menu.addAction('Tap up')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/up.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.tap_up)

            ra5 = menu.addAction('Tap down')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/down.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.tap_down)

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

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            ok = yes_no_question('Do you want to remove this transformer?', 'Remove transformer')
        else:
            ok = True

        if ok:
            self.diagramScene.circuit.delete_branch(self.api_object)
            self.diagramScene.removeItem(self)

    def reduce(self):
        """
        Reduce this branch
        """
        ok = yes_no_question('Do you want to reduce this transformer?', 'Reduce transformer')

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
                self.diagramScene.parent_.add_transformer(br)
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
        templates = self.diagramScene.circuit.transformer_types
        current_template = self.api_object.template
        dlg = TransformerEditor(self.api_object, Sbase,
                                modify_on_accept=True,
                                templates=templates,
                                current_template=current_template)
        if dlg.exec_():
            pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.diagramScene.circuit.Sbase

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

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_rate_to_profile(self.api_object)

    def flip_connections(self):
        """
        Flip connections
        :return:
        """
        self.api_object.flip()

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_active_status_to_profile(self.api_object)

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

