# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QPointF
from PySide6.QtGui import QPen, QIcon, QPixmap
from PySide6.QtWidgets import (QMenu, QGraphicsTextItem, QDialog, QTableView, QVBoxLayout, QHBoxLayout,
                               QPushButton, QSplitter, QFrame, QSpacerItem, QSizePolicy)
from GridCalEngine.Core.Devices.Injections.generator import Generator, DeviceType
from GridCalEngine.Core.Devices.Injections.generator_q_curve import GeneratorQCurve
from GridCalEngine.basic_structures import Mat, Vec
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Circle
from GridCal.Gui.GridEditorWidget.matplotlibwidget import MatplotlibWidget
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.messages import yes_no_question, info_msg, warning_msg, error_msg
from GridCal.Gui.GridEditorWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.SolarPowerWizard.solar_power_wizzard import SolarPvWizard
from GridCal.Gui.WindPowerWizard.wind_power_wizzard import WindFarmWizard


class GeneratorQCurveEditorTableModel(QAbstractTableModel):
    """
    GeneratorQCurveEditorTableModel
    """

    def __init__(self, data: Mat, headers, parent=None, callback=None):
        super(GeneratorQCurveEditorTableModel, self).__init__(parent)
        self._data = data
        self._headers = headers
        self.callback = callback

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return str(self._data[index.row(), index.column()])

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            try:
                # Attempt to convert the input to a float value
                value = float(value)
            except ValueError:
                return False  # Input is not a valid float

            # Update the data in the model
            self._data[index.row(), index.column()] = value
            self.dataChanged.emit(index, index)
            if self.callback is not None:
                self.callback()

            if index.column() == 0:
                self.sortData()

            return True

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation,
                   role=Qt.ItemDataRole.DisplayRole):

        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super(GeneratorQCurveEditorTableModel, self).headerData(section, orientation, role)

    def addRow(self, rowData: Vec):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data = np.vstack([self._data, rowData])
        self.endInsertRows()

    def delRow(self, i):
        if self._data.shape[0] > 0:
            self.beginRemoveRows(QModelIndex(), i, i)
            self._data = np.delete(self._data, i, axis=0)
            self.endRemoveRows()

    def delLastRow(self):
        if self._data.shape[0] > 0:
            i = self._data.shape[0] - 1
            self.beginRemoveRows(QModelIndex(), i, i)
            self._data = np.delete(self._data, i, axis=0)
            self.endRemoveRows()

    def sortData(self):

        # Get the indices that would sort the array along the first column
        sorted_indices = np.argsort(self._data[:, 0])

        # Use the indices to reorder the rows
        self._data = self._data[sorted_indices]

        self.layoutChanged.emit()

    def getData(self):
        return self._data


class GeneratorQCurveEditor(QDialog):
    """
    GeneratorQCurveEditor
    """

    def __init__(self, q_curve: GeneratorQCurve, Qmin, Qmax, Pmin, Pmax, Snom):
        """

        :param q_curve:
        :param Qmin:
        :param Qmax:
        :param Pmin:
        :param Pmax:
        :param Snom:
        """

        super(GeneratorQCurveEditor, self).__init__()

        self.setWindowTitle("Reactive power curve editor")

        self.q_curve: GeneratorQCurve = q_curve
        self.Qmin = Qmin
        self.Qmax = Qmax
        self.Pmin = Pmin
        self.Pmax = Pmax
        self.Snom = Snom

        self.headers = ["P", "Qmin", "Qmax"]

        self.table_model = GeneratorQCurveEditorTableModel(data=self.q_curve.get_data(),
                                                           headers=self.headers,
                                                           callback=self.plot)

        self.l_frame = QFrame()
        self.r_frame = QFrame()
        self.buttons_frame = QFrame()
        self.buttons_frame.setMaximumHeight(40)

        self.l_layout = QVBoxLayout(self.l_frame)
        self.r_layout = QVBoxLayout(self.r_frame)
        self.buttons_layout = QHBoxLayout(self.buttons_frame)

        self.l_layout.setContentsMargins(0, 0, 0, 0)
        self.r_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Enable row selection
        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setModel(self.table_model)

        self.add_row_button = QPushButton("Add")
        self.add_row_button.clicked.connect(self.addRow)

        self.del_button = QPushButton("Del")
        self.del_button.clicked.connect(self.removeSelectedRow)

        # self.sort_button = QPushButton("Sort")
        # self.sort_button.clicked.connect(self.sort)

        self.buttons_layout.addWidget(self.add_row_button)
        # self.buttons_layout.addWidget(self.sort_button)
        self.buttons_layout.addSpacerItem(QSpacerItem(40, 30, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.buttons_layout.addWidget(self.del_button)

        self.l_layout.addWidget(self.table_view)
        self.l_layout.addWidget(self.buttons_frame)

        self.plotter = MatplotlibWidget()
        self.r_layout.addWidget(self.plotter)

        # Create a splitter to create a vertical split view
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.l_frame)
        splitter.addWidget(self.r_frame)

        central_layout = QVBoxLayout(self)
        central_layout.addWidget(splitter)
        central_layout.setContentsMargins(0, 0, 0, 0)

        self.plot()

    def addRow(self):
        """
        Add a new row of zeros
        :return:
        """
        self.table_model.addRow(np.zeros(3))

    def removeSelectedRow(self):
        """

        :return:
        """
        selected_indexes = self.table_view.selectionModel().selectedRows()

        if selected_indexes:
            # Assuming the selection model is set to single selection mode
            row = selected_indexes[0].row()
            self.table_model.delRow(row)
        else:
            # if no selection, delete the last row
            self.table_model.delLastRow()

    def sort(self):
        self.table_model.sortData()

    def collect_data(self):
        """
        Collect the data from the data model into the curve object
        """
        self.q_curve.set_data(self.table_model.getData())
        self.Snom = self.q_curve.get_Snom()
        self.Qmax = self.q_curve.get_Qmax()
        self.Qmin = self.q_curve.get_Qmin()
        self.Pmax = self.q_curve.get_Pmax()
        self.Pmin = self.q_curve.get_Pmin()

    def closeEvent(self, event):
        """
        On close, recover the data
        :param event:
        :return:
        """
        self.collect_data()

    def plot(self):
        """
        Plot the chart
        :return:
        """
        self.plotter.clear()

        self.collect_data()

        # plot the limits
        radius = self.q_curve.get_Snom()
        theta = np.linspace(0, 2 * np.pi, 100)
        x = radius * np.cos(theta)
        y = radius * np.sin(theta)
        self.plotter.plot(x, y,
                          color='gray',
                          marker=None,
                          linestyle='dotted',
                          linewidth=1,
                          markersize=4)

        # plot the data
        self.q_curve.plot(ax=self.plotter.canvas.ax)

        self.plotter.redraw()
        self.plotter.canvas.fig.tight_layout()

    # def cellDoubleClicked(self, index):
    #     # Double-clicked on the phantom row
    #     column_name = self.headers[index.column()]
    #     value, ok = QInputDialog.getDouble(self, f"Enter {column_name}", f"{column_name}:", 0.0, -1000.0, 1000.0, 1)
    #     if ok:
    #         self.table_model.setData(index, value, role=Qt.EditRole)


class GeneratorGraphicItem(InjectionTemplateGraphicItem):
    """
    GeneratorGraphicItem
    """

    def __init__(self, parent, api_obj: Generator, diagramScene):
        """

        :param parent:
        :param api_obj:
        :param diagramScene:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              diagramScene=diagramScene,
                                              device_type_name='generator',
                                              w=40,
                                              h=40)

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

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object],
                           self.api_object.editable_headers,
                           parent=self.diagramScene.parent().object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists={DeviceType.Technology.value: self.diagramScene.circuit.technologies,
                                                DeviceType.FuelDevice.value: self.diagramScene.circuit.fuels,
                                                DeviceType.EmissionGasDevice.value: self.diagramScene.circuit.emission_gases,
                                                })
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """

        :param event:
        """
        self.edit()

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
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

        pen = QPen(self.color, self.width, self.style)
        self.glyph.setPen(pen)
        self.nexus.setPen(pen)
        self.label.setDefaultTextColor(self.color)

    def update_line(self, pos: QPointF):
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
            parent.y() + parent.terminal.y + 5,
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
        menu.addSection("Generator")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

        pc = menu.addAction('Voltage control')
        pc.setCheckable(True)
        pc.setChecked(self.api_object.is_controlled)
        pc.triggered.connect(self.enable_disable_control_toggle)

        pa = menu.addAction('Plot profiles')
        plot_icon = QIcon()
        plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
        pa.setIcon(plot_icon)
        pa.triggered.connect(self.plot)

        pv = menu.addAction('Solar photovoltaic wizard')
        pv_icon = QIcon()
        pv_icon.addPixmap(QPixmap(":/Icons/icons/solar_power.svg"))
        pv.setIcon(pv_icon)
        pv.triggered.connect(self.solar_pv_wizard)

        wp = menu.addAction('Wind farm wizard')
        wp_icon = QIcon()
        wp_icon.addPixmap(QPixmap(":/Icons/icons/wind_power.svg"))
        wp.setIcon(wp_icon)
        wp.triggered.connect(self.wind_farm_wizard)

        menu.addSeparator()

        da = menu.addAction('Delete')
        del_icon = QIcon()
        del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        cb = menu.addAction('Convert to battery')
        batt_icon = QIcon()
        batt_icon.addPixmap(QPixmap(":/Icons/icons/add_batt.svg"))
        cb.setIcon(batt_icon)
        cb.triggered.connect(self.to_battery)

        rabf = menu.addAction('Change bus')
        move_bus_icon = QIcon()
        move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
        rabf.setIcon(move_bus_icon)
        rabf.triggered.connect(self.change_bus)

        menu.exec_(event.screenPos())

    def to_battery(self):
        """
        Convert this generator to a battery
        """
        ok = yes_no_question('Are you sure that you want to convert this generator into a battery?',
                             'Convert generator')
        if ok:
            editor = self.diagramScene.parent()
            editor.convert_generator_to_battery(gen=self.api_object, graphic_object=self)

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this generator', 'Remove generator')
        else:
            ok = True

        if ok:
            self.diagramScene.removeItem(self.nexus)
            self.diagramScene.removeItem(self)
            if self.api_object in self.api_object.bus.generators:
                self.api_object.bus.generators.remove(self.api_object)

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

    def enable_disable_control_toggle(self):
        """
        Enable / Disable device voltage control
        """
        if self.api_object is not None:
            self.api_object.is_controlled = not self.api_object.is_controlled

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
        # time series object from the last simulation
        ts = self.diagramScene.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        dlg = GeneratorQCurveEditor(q_curve=self.api_object.q_curve,
                                    Qmin=self.api_object.Qmin,
                                    Qmax=self.api_object.Qmax,
                                    Pmin=self.api_object.Pmin,
                                    Pmax=self.api_object.Pmax,
                                    Snom=self.api_object.Snom)
        if dlg.exec():
            pass

        self.api_object.Snom = np.round(dlg.Snomm, 1) if dlg.Snom > 1 else dlg.Snom
        self.api_object.Qmin = dlg.Qmin
        self.api_object.Qmax = dlg.Qmax
        self.api_object.Pmin = dlg.Pmin
        self.api_object.Pmax = dlg.Pmax

    def solar_pv_wizard(self):
        """
        Open the appropriate editor dialogue
        :return:
        """

        if self.diagramScene.circuit.has_time_series:

            time_array = self.diagramScene.circuit.time_profile

            dlg = SolarPvWizard(time_array=time_array,
                                peak_power=self.api_object.Pmax,
                                latitude=self.api_object.bus.latitude,
                                longitude=self.api_object.bus.longitude,
                                gen_name=self.api_object.name,
                                bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == len(self.api_object.P_prof):
                        self.api_object.P_prof = dlg.P

                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")

    def wind_farm_wizard(self):
        """
        Open the appropriate editor dialogue
        :return:
        """

        if self.diagramScene.circuit.has_time_series:

            time_array = self.diagramScene.circuit.time_profile

            dlg = WindFarmWizard(time_array=time_array,
                                 peak_power=self.api_object.Pmax,
                                 latitude=self.api_object.bus.latitude,
                                 longitude=self.api_object.bus.longitude,
                                 gen_name=self.api_object.name,
                                 bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == len(self.api_object.P_prof):
                        self.api_object.P_prof = dlg.P

                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")
