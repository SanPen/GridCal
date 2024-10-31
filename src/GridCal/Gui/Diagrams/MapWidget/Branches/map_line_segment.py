# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtGui import QPen, QColor, QCursor
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsSceneMouseEvent

from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import ArrowHead
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_editor import LineEditor

from GridCalEngine.Devices.types import BRANCH_TYPES

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapLineSegment(QGraphicsLineItem):
    """
    Segment joining two NodeGraphicItem
    """

    def __init__(self, first: LineLocationGraphicItem, second: LineLocationGraphicItem, container: MapLineContainer):
        """
        Segment constructor
        :param first: NodeGraphicItem
        :param second: NodeGraphicItem
        """
        QGraphicsLineItem.__init__(self)
        self.first: LineLocationGraphicItem = first
        self.second: LineLocationGraphicItem = second
        self.container: MapLineContainer = container
        self.draw_labels = True

        self.style = Qt.PenStyle.SolidLine
        self.color = QColor(115, 115, 115, 200)  # translucent gray
        self.width = 0.1

        self.pos1: QPointF = self.first.get_center_pos()
        self.pos2: QPointF = self.second.get_center_pos()

        # arrows
        self.view_arrows = True
        self._arrow_size = self.width * 1.5
        self.arrow_p_from = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.2, under=False,
                                      text_scale=0.01, show_text=False)
        self.arrow_q_from = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.2, under=True,
                                      text_scale=0.01, show_text=False)
        self.arrow_p_to = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.8, under=False,
                                    text_scale=0.01, show_text=False)
        self.arrow_q_to = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.8, under=True,
                                    text_scale=0.01, show_text=False)

        # set callbacks
        self.first.add_position_change_callback(self.set_from_side_coordinates)
        self.second.add_position_change_callback(self.set_to_side_coordinates)

        self.set_colour(self.color, self.style)
        self.update_endings()
        self.needsUpdate = True
        self.setZValue(0)

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    @property
    def api_object(self) -> BRANCH_TYPES:
        """

        :return:
        """
        return self.container.api_object

    @property
    def editor(self) -> GridMapWidget:
        """

        :return:
        """
        return self.container.editor

    def set_width(self, width: float):
        """

        :param width:
        :return:
        """
        pen = self.pen()
        pen.setWidthF(width)
        self.setPen(pen)

    def set_arrow_scale(self, width: float):
        """

        :param width:
        :return:
        """
        self.arrow_p_from.setScale(width)
        self.arrow_q_from.setScale(width)
        self.arrow_p_to.setScale(width)
        self.arrow_q_to.setScale(width)

    def set_colour(self, color: QColor, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param style: PenStyle instance
        :return:
        """

        pen = QPen(color, self.width, style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        self.setPen(pen)
        self.arrow_p_from.set_colour(color, self.arrow_p_from.w, style)
        self.arrow_q_from.set_colour(color, self.arrow_q_from.w, style)
        self.arrow_p_to.set_colour(color, self.arrow_p_to.w, style)
        self.arrow_q_to.set_colour(color, self.arrow_q_to.w, style)

    def set_from_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos1 = QPointF(x, y)
        self.update_endings()

    def set_to_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos2 = QPointF(x, y)
        self.update_endings()

    def update_endings(self, force=False) -> None:
        """
        Update the endings of this segment
        """
        self.setLine(QLineF(self.pos1, self.pos2))

        if self.api_object is not None:

            # arrows
            if self.view_arrows:
                self.arrow_p_from.redraw()
                self.arrow_q_from.redraw()
                self.arrow_p_to.redraw()
                self.arrow_q_to.redraw()

    def end_update(self) -> None:
        """

        :return:
        """
        self.first.needsUpdate = False
        self.second.needsUpdate = False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        :return:
        """
        menu = QMenu()

        menu.addSection("Line")

        add_menu_entry(menu=menu,
                       text="Active",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.container.api_object.active)

        add_menu_entry(menu=menu,
                       text="Draw labels",
                       function_ptr=self.enable_disable_label_drawing,
                       checkeable=True,
                       checked_value=self.draw_labels)

        add_menu_entry(menu=menu,
                       text="Editor",
                       function_ptr=self.call_editor,
                       icon_path=":/Icons/icons/edit.svg")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       function_ptr=self.plot_profiles,
                       icon_path=":/Icons/icons/plot.svg")

        add_menu_entry(menu=menu,
                       text="Assign rate to profile",
                       function_ptr=self.assign_rate_to_profile,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        add_menu_entry(menu=menu,
                       text="Assign active state to profile",
                       function_ptr=self.assign_status_to_profile,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        add_menu_entry(menu=menu,
                       text="Add point",
                       function_ptr=self.add_path_node,
                       icon_path=":/Icons/icons/cn_icon.svg")

        # add_menu_entry(menu=menu,
        #                text="Add substation here",
        #                function_ptr=self.add_substation_here,
        #                icon_path=":/Icons/icons/substation.svg")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       function_ptr=self.remove,
                       icon_path=":/Icons/icons/delete3.svg")

        menu.exec_(event.screenPos())

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.get_time_number() > 0:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.editor.set_active_status_to_profile(self.api_object, override_question=True)

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
        self.set_colour(self.color, self.style)

    def enable_disable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = not self.draw_labels

    def call_editor(self):
        """
        Call the line editor
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        Vnom = self.api_object.get_max_bus_nominal_voltage()
        templates = list()

        for lst in [self.editor.circuit.sequence_line_types,
                    self.editor.circuit.underground_cable_types,
                    self.editor.circuit.overhead_line_types]:
            for temp in lst:
                if Vnom == temp.Vnom:
                    templates.append(temp)

        current_template = self.api_object.template
        dlg = LineEditor(line=self.api_object, Sbase=Sbase, frequency=self.editor.circuit.fBase,
                         templates=templates, current_template=current_template)
        dlg.exec()

    def plot_profiles(self) -> None:
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_branches().index(self.api_object)
        self.editor.plot_branch(i, self.api_object)

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_active_status_to_profile(self.api_object)

    def add_path_node(self):
        """
        Add a path to the container by adding a new graphical segment
        """

        if len(self.container.nodes_list) == 0:
            self.container.insert_new_node_at_position(0)

        elif len(self.container.nodes_list) == 1:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(1)
            else:
                self.container.insert_new_node_at_position(0)
        else:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(len(self.container.nodes_list))

            elif self.second == self.container.substation_from() or self.first == self.container.substation_from():
                self.container.insert_new_node_at_position(0)

            else:
                if self.first.index > self.second.index:
                    self.container.insert_new_node_at_position(self.second.index)

                elif self.first.index < self.second.index:
                    self.container.insert_new_node_at_position(self.second.index)

    def add_substation_here(self):
        """
        Split the line
        :return:
        """
        # TODO implement:
        # The container of this segment must be split into two new containers
        # and in the middle, we need to create a substation object

        # self.editor.split_line_in_out(line_graphics=self)
        pass

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            dtype = self.api_object.device_type.value
            ok = yes_no_question(f'Do you want to remove the {dtype} {self.api_object.name}?',
                                 f'Remove {dtype}')
        else:
            ok = True

        if ok:
            self.editor.circuit.delete_branch(obj=self.api_object)
            self.editor.delete_diagram_element(device=self.api_object)

    def set_arrows_with_power(self, Sf: complex, St: complex) -> None:
        """
        Set the arrow directions
        :param Sf: Complex power from
        :param St: Complex power to
        """

        if Sf is not None:
            if St is None:
                St = -Sf

            Pf = Sf.real
            Qf = Sf.imag
            Pt = St.real
            Qt_ = St.imag
            self.arrow_p_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
            self.arrow_q_from.set_value(Qf, True, Qf < 0, name="Qf", units="MVAr", draw_label=self.draw_labels)
            self.arrow_p_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
            self.arrow_q_to.set_value(Qt_, True, Qt_ > 0, name="Qt", units="MVAr", draw_label=self.draw_labels)

    def set_arrows_with_hvdc_power(self, Pf: float, Pt: float) -> None:
        """
        Set the arrow directions
        :param Pf: Complex power from
        :param Pt: Complex power to
        """
        self.arrow_p_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_q_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_p_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
        self.arrow_q_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
