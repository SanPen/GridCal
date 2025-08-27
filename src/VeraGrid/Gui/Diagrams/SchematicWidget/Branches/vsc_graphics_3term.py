# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING, List, Union, cast
from PySide6.QtCore import Qt, QPoint, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QCursor, QTransform
from PySide6.QtWidgets import QMenu, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent

from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import RoundTerminalItem
from VeraGrid.Gui.Diagrams.generic_graphics import GenericDiagramWidget, ACTIVE, DEACTIVATED
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import DeviceType, ConverterControlType, \
    TerminalType  # Assuming VSC controls might be relevant later

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import \
        LineGraphicTemplateItem  # For type hints if needed later
    from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import RoundTerminalItem, BarTerminalItem


class VscGraphicItem3Term(GenericDiagramWidget, QGraphicsRectItem):
    """
    Graphics item for the 3-Terminal VSC converter
    """

    def __init__(self,
                 editor: SchematicWidget,
                 api_object: VSC,
                 pos: QPoint = None,
                 parent=None,
                 draw_labels: bool = True):
        """
        Constructor for the 3-Terminal VSC Graphic Item.

        :param editor: SchematicWidget instance
        :param api_object: VSC API object
        :param pos: Initial position
        :param parent: Parent item
        :param draw_labels: Whether to draw labels
        """
        GenericDiagramWidget.__init__(self, parent=parent, api_object=api_object, editor=editor,
                                      draw_labels=draw_labels)
        QGraphicsRectItem.__init__(self, parent=parent)

        # Make it a square
        self.w = 60  # Width of the VSC symbol
        self.h = self.w  # Height of the VSC symbol
        self.setRect(0.0, 0.0, self.w, self.h)

        self.draw_labels = draw_labels

        # Color and style based on active state
        self.pen_width = 2
        if self.api_object.active:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']
        else:
            self.color = DEACTIVATED['color']

        # Setup pen, brush, flags and cursor
        self.setPen(QPen(self.color, self.pen_width, self.style))
        self.setBrush(Qt.BrushStyle.NoBrush)  # Set transparent background
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        if pos is not None:
            self.setPos(pos)
        else:
            self.setPos(QPoint(0, 0))

        # --- Create Terminals ---
        # Terminal positions (relative to the item's top-left corner 0,0)
        # AC terminal on the right middle
        t_ac_pos = QPointF(self.w, self.h / 2)
        # DC+ terminal on the left top
        t_dc_p_pos = QPointF(-10, self.h * 0.2)
        # DC- terminal on the left bottom
        t_dc_n_pos = QPointF(-10, self.h * 0.8)

        # self.terminals: List[RoundTerminalItem] = list()
        self.terminal_ac: RoundTerminalItem | None = None
        self.terminal_dc_p: RoundTerminalItem | None = None
        self.terminal_dc_n: RoundTerminalItem | None = None
        self.conn_line_ac: LineGraphicTemplateItem | None = None
        self.conn_line_dc_p: LineGraphicTemplateItem | None = None
        self.conn_line_dc_n: LineGraphicTemplateItem | None = None

        # AC Terminal (Index 0)
        self.terminal_ac = RoundTerminalItem("ac", parent=self, editor=self.editor, terminal_type=TerminalType.AC)
        self.terminal_ac.setPos(t_ac_pos)
        self.terminal_ac.setRotation(0)  # Points right
        self.terminal_ac.setPen(QPen(self.color, self.pen_width, self.style))

        # DC+ Terminal (Index 1)
        self.terminal_dc_p = RoundTerminalItem("dc_p", parent=self, editor=self.editor, terminal_type=TerminalType.DC_P)
        self.terminal_dc_p.setPos(t_dc_p_pos)
        self.terminal_dc_p.setRotation(0)  # Points left
        self.terminal_dc_p.setPen(QPen(self.color, self.pen_width, self.style))

        # DC- Terminal (Index 2)
        self.terminal_dc_n = RoundTerminalItem("dc_n", parent=self, editor=self.editor, terminal_type=TerminalType.DC_N)
        self.terminal_dc_n.setPos(t_dc_n_pos)
        self.terminal_dc_n.setRotation(0)  # Points left
        self.terminal_dc_n.setPen(QPen(self.color, self.pen_width, self.style))

        self.set_terminal_tooltips()

        # self.setRotation(180)

    @property
    def api_object(self) -> VSC:
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        return self._editor

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Paint the VSC symbol."""
        # Draw the main rectangle (square)
        painter.setPen(QPen(self.color, self.pen_width, self.style))
        painter.setBrush(Qt.BrushStyle.NoBrush)  # Ensure transparent background
        painter.drawRect(self.rect())

        # Draw a diagonal line from top-right to bottom-left
        pen = QPen(self.color, self.pen_width)
        painter.setPen(pen)
        painter.drawLine(QPoint(self.w, 0), QPoint(0, self.h))

        # Draw AC/DC symbols inside the box near terminals
        text_rect_size = 15
        painter.drawText(
            QRectF(self.w * 0.8 - text_rect_size / 2, self.h / 2 - text_rect_size / 2 * 1.3, text_rect_size,
                   text_rect_size), Qt.AlignmentFlag.AlignCenter, "~")
        painter.drawText(QRectF(self.w * 0.15 - text_rect_size / 2, self.h * 0.35 - text_rect_size / 2, text_rect_size,
                                text_rect_size), Qt.AlignmentFlag.AlignCenter, "+")
        painter.drawText(QRectF(self.w * 0.15 - text_rect_size / 2, self.h * 0.65 - text_rect_size / 2, text_rect_size,
                                text_rect_size), Qt.AlignmentFlag.AlignCenter, "-")

    def set_terminal_tooltips(self):
        """Set tooltips for the terminals."""
        if self.api_object:
            self.terminal_ac.setToolTip(
                f"AC Terminal ({self.api_object.bus_to.name if self.api_object.bus_to else 'Unconnected'})")
            self.terminal_dc_p.setToolTip(
                f"DC+ Terminal ({self.api_object.bus_from.name if self.api_object.bus_from else 'Unconnected'})")
            self.terminal_dc_n.setToolTip(
                f"DC- Terminal ({self.api_object.bus_dc_n.name if self.api_object.bus_dc_n else 'Unconnected'})")

    def update_conn(self):
        """Update the connection lines attached to this item."""
        if self.conn_line_ac is not None:
            self.conn_line_ac.update_ports()
        if self.conn_line_dc_p is not None:
            self.conn_line_dc_p.update_ports()
        if self.conn_line_dc_n is not None:
            self.conn_line_dc_n.update_ports()

    def get_associated_widgets(self) -> List[LineGraphicTemplateItem]:
        """Return the graphical line items connected to this VSC."""
        return [self.conn_line_ac, self.conn_line_dc_p, self.conn_line_dc_n]

    def get_extra_graphics(self):
        """Return terminals associated with this widget."""
        return [self.terminal_ac, self.terminal_dc_p, self.terminal_dc_n]

    def recolour_mode(self):
        """Change the colour according to the system theme and active state."""
        if self.api_object is None:
            return

        if self.api_object.active:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        pen = QPen(self.color, self.pen_width, self.style)
        self.setPen(pen)

        self.terminal_ac.setPen(pen)
        self.terminal_dc_p.setPen(pen)
        self.terminal_dc_n.setPen(pen)

        if self.conn_line_ac is not None:
            self.conn_line_ac.recolour_mode()
        if self.conn_line_dc_p is not None:
            self.conn_line_dc_p.recolour_mode()
        if self.conn_line_dc_n is not None:
            self.conn_line_dc_n.recolour_mode()

        self.update()  # Request repaint

    def set_enable(self, val=True):
        """Set the enable value, graphically and in the API."""
        self.api_object.active = val
        self.recolour_mode()

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """Handle mouse move event."""
        super().mouseMoveEvent(event)
        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=self.h,
                                           r=self.rotation(),
                                           graphic_object=self)
        self.update_conn()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press: select item and show in editor."""
        super().mousePressEvent(event)  # Handle selection
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseDoubleClickEvent(self, event):
        """ On double-click, potentially open an editor (optional)."""
        # Currently no specific editor for VSC, but could be added.
        # self.edit()
        pass

    def delete(self):
        """Delete the VSC and its connections."""
        # Remove connections first
        self.remove_connection(self.conn_line_ac)
        self.remove_connection(self.conn_line_dc_p)
        self.remove_connection(self.conn_line_dc_n)

        # Remove the item itself
        self.editor.diagram_scene.removeItem(self)

    def set_connection(self, terminal_type: TerminalType, bus: Bus, conn_line: LineGraphicTemplateItem):
        """Set a connection to a specific terminal."""

        success = False
        # Check type compatibility and update API / store line
        if terminal_type == TerminalType.OTHER:
            print(f"Error: Invalid terminal type {terminal_type} for VSC {self.api_object.name}")

        elif terminal_type == TerminalType.AC:
            if bus.is_dc:
                self.editor.gui.show_error_toast(
                    f"Connecting AC terminal of VSC '{self.api_object.name}' to DC bus '{bus.name}'")
            elif self.conn_line_ac is not None:
                self.editor.gui.show_error_toast(f"AC terminal of VSC {self.api_object.name} is already connected.")
            else:
                self.api_object.bus_to = bus
                self.conn_line_ac = conn_line
                self.set_terminal_tooltips()
                success = True

        elif terminal_type == TerminalType.DC_P:
            if not bus.is_dc:
                self.editor.gui.show_error_toast(
                    f"Connecting DC+ terminal of VSC '{self.api_object.name}' to AC bus '{bus.name}'")
            elif self.conn_line_dc_p is not None:
                self.editor.gui.show_error_toast(f"AC terminal of VSC {self.api_object.name} is already connected.")
            else:
                self.api_object.bus_from = bus
                self.conn_line_dc_p = conn_line
                self.set_terminal_tooltips()
                success = True

        elif terminal_type == TerminalType.DC_N:
            if not bus.is_dc:
                self.editor.gui.show_error_toast(
                    f"Connecting DC- terminal of VSC '{self.api_object.name}' to AC bus '{bus.name}'")
            elif self.conn_line_dc_n is not None:
                self.editor.gui.show_error_toast(f"DC- terminal of VSC {self.api_object.name} is already connected.")
            else:
                self.api_object.bus_dc_n = bus
                self.conn_line_dc_n = conn_line
                self.set_terminal_tooltips()
                success = True

        return success

    def redraw(self):
        """
        Redraw method - only recalculate position if VSC doesn't have saved coordinates
        :return:
        """
        # Only recalculate position if the VSC is at the default position (close to 0, 0)
        # This preserves saved positions when loading from file
        current_pos = self.pos()
        # Use small tolerance to handle floating-point precision issues
        if abs(current_pos.x()) < 1.0 and abs(current_pos.y()) < 1.0:
            # Only do automatic positioning if we're near the origin
            h1 = self.terminal_ac.pos().y() - (self.terminal_dc_p.pos().y() + self.terminal_dc_n.pos().y()) / 2.0
            b1 = self.terminal_ac.pos().x() - (self.terminal_dc_p.pos().x() + self.terminal_dc_n.pos().x()) / 2.0
            ang = np.arctan2(h1, b1)
            h2 = self.rect().height() / 2.0
            w2 = self.rect().width() / 2.0
            a = h2 * np.cos(ang) - w2 * np.sin(ang)
            b = w2 * np.sin(ang) + h2 * np.cos(ang)

            center = (self.terminal_ac.pos() + (
                        self.terminal_dc_p.pos() + self.terminal_dc_n.pos()) * 0.5) * 0.5 - QPointF(a, b)

            transform = QTransform()
            transform.translate(center.x(), center.y())
            transform.rotate(np.rad2deg(ang))
            self.setTransform(transform)
        # If we're not near the origin, preserve the current position (likely loaded from file)

    def remove_connection(self, conn_line: LineGraphicTemplateItem):
        """Remove a connection from a specific terminal."""
        if conn_line is None:
            return
        else:
            line = conn_line
            # Remove the line from the scene
            if line.scene():
                line.scene().removeItem(line)
            # Optionally clear the bus/cn reference in the api_object
            if line == self.conn_line_ac:
                self.api_object.bus_to = None
            elif line == self.conn_line_dc_p:
                self.api_object.bus_from = None
            elif line == self.conn_line_dc_n:
                self.api_object.bus_dc_n = None
            self.set_terminal_tooltips()

    def contextMenuEvent(self, event):
        """Show context menu."""
        if self.api_object is not None:
            menu = QMenu()

            # Enable/Disable
            pe = menu.addAction('Enable/Disable')
            pe_icon = QIcon()
            if self.api_object.active:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/uncheck_all.svg"))
            else:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/check_all.svg"))
            pe.setIcon(pe_icon)
            pe.triggered.connect(lambda: self.set_enable(not self.api_object.active))

            # Draw Labels (if applicable)
            # add_menu_entry(menu=menu,
            #                text="Draw labels",
            #                function_ptr=self.enable_disable_label_drawing, # Needs implementation if label drawing is kept
            #                checkeable=True,
            #                checked_value=self.draw_labels)

            # Delete
            menu.addSeparator()
            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.delete)

            # --- Add back original control/profile actions ---
            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Control V AC from DC+",
                           function_ptr=self.control_v_from,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Control V AC from AC",
                           function_ptr=self.control_v_to,
                           icon_path=":/Icons/icons/edit.svg")

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

            menu.exec_(event.screenPos())
        else:
            pass

    def control_v_from(self):
        """
        Set control mode to regulate DC voltage based on DC+ side (Interpretation).
        Sets control1 to Vm_dcp.
        """
        if self.api_object.bus_to and self.api_object.bus_from:
            self.api_object.control1 = ConverterControlType.Vm_dc
            self.api_object.control1_dev = self.api_object.bus_from
            self.api_object.control1_val = 1.0  # Default to 1.0 pu

            print(f"VSC {self.api_object.name} control set: Control1=Vm_dcp (Bus: {self.api_object.bus_from.name})")
            self.editor.set_editor_model(api_object=self.api_object)  # Refresh editor view
        else:
            print("Error: Cannot set control_v_from, DC+ bus not connected.")

    def control_v_to(self):
        """
        Set control mode to regulate AC voltage based on AC side itself.
        Sets control1 to Vm_ac (controlling AC bus).
        Leaves control2 as is, or sets it to something default like Pac if necessary.
        """
        if self.api_object.bus_to:
            self.api_object.control1 = ConverterControlType.Vm_ac
            self.api_object.control1_dev = self.api_object.bus_to
            self.api_object.control1_val = 1.0  # Default to 1.0 pu

            print(f"VSC {self.api_object.name} control set: Control1=Vm_ac (Bus: {self.api_object.bus_to.name})")
            self.editor.set_editor_model(api_object=self.api_object)  # Refresh editor view
        else:
            print("Error: Cannot set control_v_to, AC bus not connected.")

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self._editor.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self._editor.set_active_status_to_profile(self.api_object)

    def plot_profiles(self) -> None:
        """
        Plot the time series profiles
        @return:
        """
        pass

    def assign_bus_to_vsc(self, terminal_vsc: RoundTerminalItem, bus_vsc:  RoundTerminalItem | BarTerminalItem) -> bool:
        """
        Assign the connected bus to a three-terminal VSC
        :return: if the connection was successful
        """
        if terminal_vsc.terminal_type == TerminalType.AC:
            if not bus_vsc.parent.api_object.is_dc:
                self.api_object.bus_to = bus_vsc.parent.api_object
                return True
            else:
                return False

        elif terminal_vsc.terminal_type == TerminalType.DC_P:
            if bus_vsc.parent.api_object.is_dc:
                self.api_object.bus_from = bus_vsc.parent.api_object
                return True
            else:
                return False

        elif terminal_vsc.terminal_type == TerminalType.DC_N:
            if bus_vsc.parent.api_object.is_dc:
                self.api_object.bus_dc_n = bus_vsc.parent.api_object
                return True
            else:
                return False

        else:
            print('Error in the VSC connection!')
            return False
