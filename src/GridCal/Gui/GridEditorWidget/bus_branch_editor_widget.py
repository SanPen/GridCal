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
import sys
import os
import numpy as np
import pandas as pd
from typing import List, Dict, Union, Tuple
from collections.abc import Callable
import networkx as nx
import pyproj

from PySide6.QtCore import (Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray,
                            QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen,
                           QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent)
from PySide6.QtWidgets import (QApplication, QGraphicsView, QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame,
                               QSplitter, QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsSceneMouseEvent,
                               QGraphicsItem)
from PySide6.QtSvg import QSvgGenerator

from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.Devices.Substation import Bus
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Branches.line import Line
from GridCalEngine.Core.Devices.Branches.dc_line import DcLine
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Core.Devices.Branches.vsc import VSC
from GridCalEngine.Core.Devices.Branches.upfc import UPFC
from GridCalEngine.Core.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Core.Devices.Branches.transformer3w import Transformer3W, Winding
from GridCalEngine.Core.Devices.Injections.generator import Generator
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Core.Devices.Diagrams.bus_branch_diagram import BusBranchDiagram
from GridCalEngine.Core.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.basic_structures import Vec, CxVec, IntVec

from GridCal.Gui.GridEditorWidget.terminal_item import TerminalItem
from GridCal.Gui.GridEditorWidget.substation.bus_graphics import BusGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.line_graphics import LineGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.winding_graphics import WindingGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.dc_line_graphics import DcLineGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.hvdc_graphics import HvdcGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.vsc_graphics import VscGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.upfc_graphics import UpfcGraphicItem
from GridCal.Gui.GridEditorWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from matplotlib import pyplot as plt

'''
Dependencies:

GridEditor {QSplitter}
 |
  - EditorGraphicsView {QGraphicsView} (Handles the drag and drop)
 |   |
  ---- DiagramScene {QGraphicsScene}
        |
         - MultiCircuit (Calculation engine)
        |
         - Graphic Objects: (BusGraphicItem, BranchGraphicItem, LoadGraphicItem, ...)


The graphic objects need to call the API objects and functions inside the MultiCircuit instance.
To do this the graphic objects call "parent.circuit.<function or object>"
'''


def toQBytesArray(val: str):
    """

    :param val:
    :return:
    """
    data = QByteArray()
    stream = QDataStream(data, QIODevice.WriteOnly)
    stream.writeQString(val)
    return data


class LibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    This is the list of draggable items
    """

    def __init__(self, parent=None):
        """
        Items model to host the draggable icons
        @param parent:
        """
        QStandardItemModel.__init__(self, parent)

    def mimeTypes(self) -> List[str]:
        """

        @return:
        """
        return ['component/name']

    def mimeData(self, idxs: List[QModelIndex]) -> QMimeData:
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

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


class DiagramScene(QGraphicsScene):
    """
    DiagramScene
    """

    def __init__(self, parent: "BusBranchEditorWidget", circuit: MultiCircuit):
        """

        :param parent:
        :param circuit:
        """
        super(DiagramScene, self).__init__(parent)
        self.parent_ = parent
        self.circuit = circuit
        self.results_dictionary = dict()

    def set_results_to_plot(self, all_threads: List[DriverTemplate]):
        """

        :param all_threads:
        :return:
        """
        self.results_dictionary = {thr.tpe: thr for thr in all_threads if thr is not None}

    def plot_bus(self, i, api_object):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: API object
        :return:
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        # ax_2 = fig.add_subplot(212)

        # set time
        x = self.circuit.time_profile

        if x is not None:
            if len(x) > 0:

                # search available results
                power_data = api_object.get_active_injection_profiles_dictionary()
                voltage = dict()

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.TimeSeries_run:
                                voltage[key] = np.abs(driver.results.voltage[:, i])

                # Injections
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_1.set_title('Power', fontsize=14)
                    ax_1.set_ylabel('Injections [MW]', fontsize=11)
                    df.plot.area(ax=ax_1)

                # voltage
                if len(voltage.keys()):
                    ax_2 = fig.add_subplot(212, sharex=ax_1)
                    df = pd.DataFrame(data=voltage, index=x)
                    ax_2.set_title('Time', fontsize=14)
                    ax_2.set_ylabel('Voltage [p.u]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def plot_branch(self, i: int, api_object: Union[Line, DcLine, Transformer2W, VSC, UPFC]):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: API object
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        ax_2 = fig.add_subplot(212)

        # set time
        x = self.circuit.time_profile
        x_cl = x

        if x is not None:
            if len(x) > 0:

                p = np.arange(len(x)).astype(float) / len(x)

                # search available results
                power_data = dict()
                loading_data = dict()
                loading_st_data = None
                loading_clustering_data = None
                power_clustering_data = None

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.TimeSeries_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.ClusteringTimeSeries_run:
                                x_cl = x[driver.sampled_time_idx]
                                power_clustering_data = driver.results.Sf.real[:, i]
                                loading_clustering_data = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.LinearAnalysis_TS_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            # elif key == SimulationTypes.NetTransferCapacityTS_run:
                            #     power_data[key.value] = driver.results.atc[:, i]
                            #     atc_perc = driver.results.atc[:, i] / (api_object.rate_prof + 1e-9)
                            #     loading_data[key.value] = np.sort(np.abs(atc_perc * 100.0))

                            elif key == SimulationTypes.ContingencyAnalysisTS_run:
                                power_data[key.value] = driver.results.worst_flows.real[:, i]
                                loading_data[key.value] = np.sort(
                                    np.abs(driver.results.worst_loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.OPFTimeSeries_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.StochasticPowerFlow:
                                loading_st_data = np.sort(np.abs(driver.results.loading_points.real[:, i] * 100.0))

                # add the rating
                # power_data['Rates+'] = api_object.rate_prof
                # power_data['Rates-'] = -api_object.rate_prof

                # loading
                if len(loading_data.keys()):
                    df = pd.DataFrame(data=loading_data, index=p)
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_clustering_data is not None:
                    p_st = np.arange(len(loading_clustering_data)).astype(float) / len(loading_clustering_data)
                    df = pd.DataFrame(data=loading_clustering_data,
                                      index=p_st,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_st_data is not None:
                    p_st = np.arange(len(loading_st_data)).astype(float) / len(loading_st_data)
                    df = pd.DataFrame(data=loading_st_data,
                                      index=p_st,
                                      columns=[SimulationTypes.StochasticPowerFlow.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                # power
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)
                    ax_2.plot(x, api_object.rate_prof, c='gray', linestyle='dashed', linewidth=1)
                    ax_2.plot(x, -api_object.rate_prof, c='gray', linestyle='dashed', linewidth=1)

                if power_clustering_data is not None:
                    df = pd.DataFrame(data=power_clustering_data,
                                      index=x_cl,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def plot_hvdc_branch(self, i: int, api_object: HvdcLine):
        """
        HVDC branch
        :param i: index of the object
        :param api_object: HvdcGraphicItem
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        # ax_2 = fig.add_subplot(212, sharex=ax_1)
        ax_2 = fig.add_subplot(212)

        # set time
        x = self.circuit.time_profile
        x_cl = x

        if x is not None:
            if len(x) > 0:

                p = np.arange(len(x)).astype(float) / len(x)

                # search available results
                power_data = dict()
                loading_data = dict()
                loading_st_data = None
                loading_clustering_data = None
                power_clustering_data = None

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.TimeSeries_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.ClusteringTimeSeries_run:
                                x_cl = x[driver.sampled_time_idx]
                                power_clustering_data = driver.results.hvdc_Pf[:, i]
                                loading_clustering_data = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.LinearAnalysis_TS_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.OPFTimeSeries_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                # add the rating
                # power_data['Rates+'] = api_object.rate_prof
                # power_data['Rates-'] = -api_object.rate_prof

                # loading
                if len(loading_data.keys()):
                    df = pd.DataFrame(data=loading_data, index=p)
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_clustering_data is not None:
                    p_st = np.arange(len(loading_clustering_data)).astype(float) / len(loading_clustering_data)
                    df = pd.DataFrame(data=loading_clustering_data,
                                      index=p_st,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_st_data is not None:
                    p_st = np.arange(len(loading_st_data)).astype(float) / len(loading_st_data)
                    df = pd.DataFrame(data=loading_st_data,
                                      index=p_st,
                                      columns=[SimulationTypes.StochasticPowerFlow.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                # power
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)
                    ax_2.plot(x, api_object.rate_prof, c='gray', linestyle='dashed', linewidth=1)
                    ax_2.plot(x, -api_object.rate_prof, c='gray', linestyle='dashed', linewidth=1)

                if power_clustering_data is not None:
                    df = pd.DataFrame(data=power_clustering_data,
                                      index=x_cl,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def set_rate_to_profile(self, api_object):
        """

        :param api_object:
        """
        if api_object is not None:
            if api_object.rate_prof is not None:
                quit_msg = str(api_object.name) + \
                           "\nAre you sure that you want to overwrite the rates profile with the snapshot value?"
                reply = QMessageBox.question(self.parent_, 'Overwrite the profile', quit_msg,
                                             QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)

                if reply == QMessageBox.StandardButton.Yes.value:
                    api_object.rate_prof *= 0
                    api_object.rate_prof += api_object.rate

    def set_active_status_to_profile(self, api_object, override_question=False):
        """

        :param api_object:
        :param override_question:
        :return:
        """
        if api_object is not None:
            if api_object.active_prof is not None:
                if not override_question:
                    quit_msg = str(api_object.name) + \
                               "\nAre you sure that you want to overwrite the active profile with the snapshot value?"
                    reply = QMessageBox.question(self.parent_, 'Overwrite the active profile', quit_msg,
                                                 QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
                    ok = reply == QMessageBox.StandardButton.Yes
                else:
                    ok = True

                if ok:
                    shape = api_object.active_prof.shape
                    if api_object.active:
                        api_object.active_prof = np.ones(shape, dtype=bool)
                    else:
                        api_object.active_prof = np.zeros(shape, dtype=bool)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.scene_mouse_move_event(event)

        # call the parent event
        super(DiagramScene, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.scene_mouse_release_event(event)

        # call mouseReleaseEvent on "me" (continue with the rest of the actions)
        super(DiagramScene, self).mouseReleaseEvent(event)


class EditorGraphicsView(QGraphicsView):
    """
    EditorGraphicsView (Handles the drag and drop)
    """

    def __init__(self, diagram_scene: DiagramScene, editor: "BusBranchEditorWidget"):
        """
        Editor where the diagram is displayed
        @param diagram_scene: DiagramScene object
        @param editor: BusBranchEditorWidget
        """
        QGraphicsView.__init__(self, diagram_scene)
        self._zoom = 0
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setMouseTracking(True)
        self.setInteractive(True)
        self.editor = editor
        self.diagram_scene: DiagramScene = diagram_scene
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignCenter)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """

        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Move element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Create an element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            obj_type = event.mimeData().data('component/name')
            bus_data = toQBytesArray('Bus')
            tr3w_data = toQBytesArray('3W-Transformer')

            point0 = self.mapToScene(event.position().x(), event.position().y())
            x0 = point0.x()
            y0 = point0.y()

            if bus_data == obj_type:
                name = 'Bus ' + str(len(self.diagram_scene.circuit.buses))

                obj = Bus(name=name,
                          # area=self.diagram_scene.circuit.areas[0],
                          # zone=self.diagram_scene.circuit.zones[0],
                          # substation=self.diagram_scene.circuit.substations[0],
                          # country=self.diagram_scene.circuit.countries[0],
                          vnom=self.editor.default_bus_voltage)

                graphic_object = self.add_bus(bus=obj, x=x0, y=y0, h=20, w=80)

                # weird but it's the only way to have graphical-API communication
                self.diagram_scene.circuit.add_bus(obj)

                # add to the diagram list
                self.editor.update_diagram_element(device=obj,
                                                   x=x0,
                                                   y=y0,
                                                   w=graphic_object.w,
                                                   h=graphic_object.h,
                                                   r=0,
                                                   graphic_object=graphic_object)

            elif tr3w_data == obj_type:
                name = "Transformer 3-windings" + str(len(self.diagram_scene.circuit.transformers3w))
                obj = Transformer3W(name=name)
                graphic_object = self.add_transformer_3w(elm=obj, x=x0, y=y0)

                # weird but it's the only way to have graphical-API communication
                self.diagram_scene.circuit.add_transformer3w(obj)

                # add to the diagram list
                self.editor.update_diagram_element(device=obj,
                                                   x=x0,
                                                   y=y0,
                                                   w=graphic_object.w,
                                                   h=graphic_object.h,
                                                   r=0,
                                                   graphic_object=graphic_object)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Zoom
        @param event:
        @return:
        """
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Scale the view / do the zoom
        scale_factor = 1.15
        # print(event.angleDelta().x(), event.angleDelta().y(), event.angleDelta().manhattanLength() )
        if event.angleDelta().y() > 0:
            # Zoom in
            self.zoom_in(scale_factor)

        else:
            # Zooming out
            self.zoom_out(scale_factor)

    def zoom_in(self, scale_factor: float = 1.15) -> None:
        """

        :param scale_factor:
        """
        self.scale(scale_factor, scale_factor)

    def zoom_out(self, scale_factor: float = 1.15) -> None:
        """

        :param scale_factor:
        """
        self.scale(1.0 / scale_factor, 1.0 / scale_factor)

    def add_bus(self, bus: Bus, x: int, y: int, h: int, w: int) -> BusGraphicItem:
        """
        Add bus
        :param bus: GridCal Bus object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :return: BusGraphicItem
        """

        graphic_object = BusGraphicItem(scene=self.scene(), editor=self.editor,
                                        bus=bus, x=x, y=y, h=h, w=w)
        self.diagram_scene.addItem(graphic_object)
        return graphic_object

    def add_transformer_3w(self, elm: Transformer3W, x: int, y: int) -> Transformer3WGraphicItem:
        """

        :param elm: Transformer3W
        :param x: x coordinate
        :param y: y coordinate
        :return: Transformer3WGraphicItem
        """
        graphic_object = Transformer3WGraphicItem(diagramScene=self.scene(), editor=self.editor, elm=elm)
        graphic_object.setPos(QPoint(x, y))
        self.diagram_scene.addItem(graphic_object)
        return graphic_object


class BusBranchEditorWidget(QSplitter):
    """
    GridEditorWidget
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 diagram: Union[BusBranchDiagram, None],
                 default_bus_voltage: float = 10.0):
        """
        Creates the Diagram Editor (BusBranchEditorWidget)
        :param circuit: Circuit that is handling
        :param diagram: BusBranchDiagram to use (optional)
        :param default_bus_voltage: Default bus voltages (kV)
        """

        QSplitter.__init__(self)

        # store a reference to the multi circuit instance
        self.circuit: MultiCircuit = circuit

        # diagram to store the objects locations
        self.diagram: BusBranchDiagram = diagram

        # default_bus_voltage (kV)
        self.default_bus_voltage = default_bus_voltage

        # nodes distance "explosion" factor
        self.expand_factor = 1.1

        # Widget layout and child widgets:
        self.horizontalLayout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)
        self.libraryBrowserView = QListView(self)
        self.libraryModel = LibraryModel(self)
        self.libraryModel.setColumnCount(1)

        # initialize library of items
        self.libItems = list()

        # add bus to the drag&drop
        bus_icon = QIcon()
        bus_icon.addPixmap(QPixmap(":/Icons/icons/bus_icon.svg"))
        item = QStandardItem(bus_icon, "Bus")
        item.setToolTip("Drag & drop this into the schematic")
        self.libItems.append(item)

        # add transformer3w to the drag&drop
        t3w_icon = QIcon()
        t3w_icon.addPixmap(QPixmap(":/Icons/icons/transformer3w.svg"))
        item = QStandardItem(t3w_icon, "3W-Transformer")
        item.setToolTip("Drag & drop this into the schematic")
        self.libItems.append(item)

        for i in self.libItems:
            self.libraryModel.appendRow(i)

        # set the objects list
        self.object_types = [dev.device_type.value for dev in circuit.get_objects_with_profiles_list()]

        # Actual libraryView object
        self.libraryBrowserView.setModel(self.libraryModel)
        self.libraryBrowserView.setViewMode(self.libraryBrowserView.ViewMode.ListMode)
        self.libraryBrowserView.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        # create all the schematic objects and replace the existing ones
        self.diagramScene = DiagramScene(parent=self, circuit=circuit)  # scene to add to the QGraphicsView
        self.editor_graphics_view = EditorGraphicsView(diagram_scene=self.diagramScene, editor=self)

        # create the grid name editor
        self.frame1 = QFrame()
        self.frame1_layout = QVBoxLayout()
        self.frame1_layout.setContentsMargins(0, 0, 0, 0)

        self.frame1_layout.addWidget(self.libraryBrowserView)
        self.frame1.setLayout(self.frame1_layout)

        # Add the two objects into a layout
        splitter2 = QSplitter(self)
        splitter2.addWidget(self.frame1)
        splitter2.addWidget(self.object_editor_table)
        splitter2.setOrientation(Qt.Vertical)
        self.addWidget(splitter2)
        self.addWidget(self.editor_graphics_view)

        # factor 1:10
        splitter2.setStretchFactor(0, 1)
        splitter2.setStretchFactor(1, 5)

        self.started_branch: Union[LineGraphicItem, None] = None

        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 2000)

        if diagram is not None:
            self.draw()

    def set_data(self, circuit: MultiCircuit, diagram: BusBranchDiagram):
        """
        Set the widget data and redraw
        :param circuit: MultiCircuit
        :param diagram: BusBranchDiagram
        """
        self.clear()
        self.circuit = circuit
        self.diagram = diagram
        self.draw()

    def draw(self) -> None:
        """
        Draw diagram
        :return:
        """
        # create all the schematic objects and replace the existing ones
        # self.diagramScene = DiagramScene(parent=self, circuit=self.circuit)  # scene to add to the QGraphicsView
        # self.diagramView = EditorGraphicsView(self.diagramScene, parent=self, editor=self)

        # add buses first
        bus_dict: Dict[str, BusGraphicItem] = dict()
        for category, points_group in self.diagram.data.items():

            if category == DeviceType.BusDevice.value:

                for idtag, location in points_group.locations.items():
                    # add the graphic object to the diagram view
                    graphic_object = self.editor_graphics_view.add_bus(bus=location.api_object,
                                                                       x=location.x,
                                                                       y=location.y,
                                                                       h=location.h,
                                                                       w=location.w)

                    # add circuit pointer to the bus graphic element
                    graphic_object.scene.circuit = self.circuit  # add pointer to the circuit

                    # create the bus children
                    graphic_object.create_children_widgets()

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    # add buses refference for later
                    bus_dict[idtag] = graphic_object
                    points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.Transformer3WDevice.value:

                for idtag, location in points_group.locations.items():
                    elm: Transformer3W = location.api_object

                    graphic_object = self.editor_graphics_view.add_transformer_3w(elm=elm,
                                                                                  x=location.x,
                                                                                  y=location.y)

                    bus_1_graphic_data = self.diagram.query_point(elm.bus1)
                    bus_2_graphic_data = self.diagram.query_point(elm.bus2)
                    bus_3_graphic_data = self.diagram.query_point(elm.bus3)

                    # add circuit pointer to the bus graphic element
                    graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit

                    conn1 = WindingGraphicItem(fromPort=graphic_object.terminals[0],
                                               toPort=bus_1_graphic_data.graphic_object.terminal,
                                               editor=self)

                    graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

                    conn2 = WindingGraphicItem(fromPort=graphic_object.terminals[1],
                                               toPort=bus_2_graphic_data.graphic_object.terminal,
                                               editor=self)
                    graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

                    conn3 = WindingGraphicItem(fromPort=graphic_object.terminals[2],
                                               toPort=bus_3_graphic_data.graphic_object.terminal,
                                               editor=self)
                    graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

                    graphic_object.set_position(x=location.x,
                                                y=location.y)

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    graphic_object.update_conn()
                    points_group.locations[idtag].graphic_object = graphic_object

            else:
                # pass for now...
                pass

        # add the rest of the branches
        for category, points_group in self.diagram.data.items():

            if category == DeviceType.LineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Line = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = LineGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.DCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: DcLine = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = DcLineGraphicItem(fromPort=terminal_from,
                                                           toPort=terminal_to,
                                                           editor=self,
                                                           api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.HVDCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: HvdcLine = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = HvdcGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.VscDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: VSC = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = VscGraphicItem(fromPort=terminal_from,
                                                        toPort=terminal_to,
                                                        editor=self,
                                                        api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.UpfcDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: UPFC = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = UpfcGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.Transformer2WDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Transformer2W = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = TransformerGraphicItem(fromPort=terminal_from,
                                                                toPort=terminal_to,
                                                                editor=self,
                                                                api_object=branch)

                        graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

        # last pass: arange children
        for category, points_group in self.diagram.data.items():
            if category == DeviceType.BusDevice.value:
                for idtag, location in points_group.locations.items():
                    # arrange children
                    location.graphic_object.arrange_children()

    @property
    def name(self):
        """
        Get the diagram name
        :return:
        """
        return self.diagram.name

    @name.setter
    def name(self, val: str):
        """
        Name setter
        :param val:
        :return:
        """
        self.diagram.name = val

    def update_diagram_element(self, device: EditableDevice,
                               x: int = 0, y: int = 0, w: int = 0, h: int = 0, r: float = 0,
                               graphic_object: object = None) -> None:
        """
        Set the position of a device in the diagram
        :param device: EditableDevice
        :param x: x position (px)
        :param y: y position (px)
        :param h: height (px)
        :param w: width (px)
        :param r: rotation (deg)
        :param graphic_object: Graphic object associated
        """
        self.diagram.set_point(device=device,
                               location=GraphicLocation(x=x,
                                                        y=y,
                                                        h=h,
                                                        w=w,
                                                        r=r,
                                                        api_object=device,
                                                        graphic_object=graphic_object))

    def delete_diagram_element(self, device: EditableDevice) -> None:
        """
        Delete device from the diagram registry
        :param device: EditableDevice
        """
        graphic_object: QGraphicsItem = self.diagram.delete_device(device=device)

        if graphic_object is not None:
            try:
                self.diagramScene.removeItem(graphic_object)
            except:
                pass

    def delete_diagram_elements(self, elements: List[EditableDevice]):
        """
        Delete device from the diagram registry
        :param elements:
        :return:
        """
        for elm in elements:
            self.delete_diagram_element(elm)

    def set_selected_buses(self, buses: List[Bus]):
        """
        Select the buses
        :param buses: list of Buses
        """
        for bus in buses:
            graphic_object: BusGraphicItem = self.diagram.query_point(bus).graphic_object
            graphic_object.setSelected(True)

    def get_selected_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        points_group = self.diagram.data.get(DeviceType.BusDevice.value, None)

        if points_group:

            bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.buses)}

            for bus_idtag, point in points_group.locations.items():
                if point.graphic_object.isSelected():
                    idx, bus = bus_dict[bus_idtag]
                    lst.append((idx, bus, point.graphic_object))
        return lst

    def get_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get all the buses
        :return: tuple(bus index, bus_api_object, bus_graphic_object)
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        points_group = self.diagram.data.get(DeviceType.BusDevice.value, None)

        if points_group:

            bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.buses)}

            for bus_idtag, point in points_group.locations.items():
                idx, bus = bus_dict[bus_idtag]
                lst.append((idx, bus, point.graphic_object))

        return lst

    def start_connection(self, port: TerminalItem):
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.started_branch = LineGraphicItem(fromPort=port, toPort=None, editor=self)
        # self.started_branch.bus_from = port.parent
        port.setZValue(0)
        port.process_callbacks(port.parent.pos() + port.pos())

    def scene_mouse_move_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        if self.started_branch:
            pos = event.scenePos()
            self.started_branch.setEndPos(pos)

    def scene_mouse_release_event(self, event: QGraphicsSceneMouseEvent) -> None:
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

                        self.started_branch.setToPort(item)
                        item.hosting_connections.append(self.started_branch)
                        self.started_branch.bus_to = item.parent

                        if self.started_branch.connected_between_buses():

                            if self.started_branch.should_be_a_converter():
                                # different DC status -> VSC

                                name = 'VSC ' + str(len(self.circuit.vsc_devices) + 1)
                                obj = VSC(bus_from=self.started_branch.get_bus_from(),
                                          bus_to=self.started_branch.get_bus_to(),
                                          name=name)

                                graphic_object = VscGraphicItem(fromPort=self.started_branch.fromPort,
                                                                toPort=self.started_branch.toPort,
                                                                editor=self,
                                                                api_object=obj)

                                self.update_diagram_element(device=obj,
                                                            graphic_object=graphic_object)

                            elif self.started_branch.should_be_a_dc_line():
                                # both buses are DC

                                name = 'Dc line ' + str(len(self.circuit.dc_lines) + 1)
                                obj = DcLine(bus_from=self.started_branch.get_bus_from(),
                                             bus_to=self.started_branch.get_bus_to(),
                                             name=name)

                                graphic_object = DcLineGraphicItem(fromPort=self.started_branch.fromPort,
                                                                   toPort=self.started_branch.toPort,
                                                                   editor=self,
                                                                   api_object=obj)

                                self.update_diagram_element(device=obj,
                                                            graphic_object=graphic_object)

                            elif self.started_branch.should_be_a_transformer():
                                name = 'Transformer ' + str(len(self.circuit.transformers2w) + 1)
                                obj = Transformer2W(bus_from=self.started_branch.get_bus_from(),
                                                    bus_to=self.started_branch.get_bus_to(),
                                                    name=name)

                                graphic_object = TransformerGraphicItem(fromPort=self.started_branch.fromPort,
                                                                        toPort=self.started_branch.toPort,
                                                                        editor=self,
                                                                        api_object=obj)

                                self.update_diagram_element(device=obj,
                                                            graphic_object=graphic_object)

                            else:
                                name = 'Line ' + str(len(self.circuit.lines) + 1)
                                obj = Line(bus_from=self.started_branch.get_bus_from(),
                                           bus_to=self.started_branch.get_bus_to(),
                                           name=name)

                                graphic_object = LineGraphicItem(fromPort=self.started_branch.fromPort,
                                                                 toPort=self.started_branch.toPort,
                                                                 editor=self,
                                                                 api_object=obj)

                                self.update_diagram_element(device=obj,
                                                            graphic_object=graphic_object)

                            # add the new object to the circuit
                            self.circuit.add_branch(obj)

                            # update the connection placement
                            graphic_object.fromPort.update()
                            graphic_object.toPort.update()

                            # set the connection placement
                            graphic_object.setZValue(-1)

                        elif self.started_branch.conneted_between_tr3_and_bus():

                            tr3_graphic_object = self.started_branch.get_from_graphic_object()
                            # obj = graphic_object.api_object

                            if self.started_branch.is_to_port_a_bus():
                                # if the bus "from" is the TR3W, the "to" is the bus
                                bus = self.started_branch.get_bus_to()
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = tr3_graphic_object.get_connection_winding(from_port=self.started_branch.fromPort,
                                                                          to_port=self.started_branch.toPort)

                            if tr3_graphic_object.connection_lines[i] is None:
                                winding_graphics = WindingGraphicItem(fromPort=self.started_branch.fromPort,
                                                                      toPort=self.started_branch.toPort,
                                                                      editor=self)

                                tr3_graphic_object.set_connection(i, bus, winding_graphics)
                                self.started_branch.fromPort.update()
                                self.started_branch.toPort.update()
                                tr3_graphic_object.update_conn()
                                self.update_diagram_element(device=winding_graphics.api_object,
                                                            graphic_object=winding_graphics)

                        elif self.started_branch.connected_between_bus_and_tr3():

                            tr3_graphic_object = self.started_branch.get_to_graphic_object()

                            if self.started_branch.is_from_port_a_bus():
                                # if the bus "to" is the TR3W, the "from" is the bus
                                bus = self.started_branch.get_bus_from()
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = tr3_graphic_object.get_connection_winding(from_port=self.started_branch.fromPort,
                                                                          to_port=self.started_branch.toPort)

                            if tr3_graphic_object.connection_lines[i] is None:
                                winding_graphics = WindingGraphicItem(fromPort=self.started_branch.fromPort,
                                                                      toPort=self.started_branch.toPort,
                                                                      editor=self)

                                tr3_graphic_object.set_connection(i, bus, winding_graphics)
                                self.started_branch.fromPort.update()
                                self.started_branch.toPort.update()
                                tr3_graphic_object.update_conn()
                                self.update_diagram_element(device=winding_graphics.api_object,
                                                            graphic_object=winding_graphics)

                        else:
                            print('unknown connection')

            # if self.started_branch.toPort is None:
            self.started_branch.remove_widget()

        # release this pointer
        self.started_branch = None

    def apply_expansion_factor(self, factor: float):
        """
        separate or get closer the drawn elements
        :param factor: expansion factor (i.e 1.1 to expand, 0.9 to get closer)
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(self.diagramScene.selectedItems()) > 0:

            # expand selection
            for item in self.diagramScene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * factor
                    y = item.pos().y() * factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                    # apply changes to the diagram coordinates
                    location = self.diagram.query_point(item.api_object)
                    if location:
                        location.x = x
                        location.y = y

        else:

            # expand all
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * factor
                    y = item.pos().y() * factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                    # apply changes to the diagram coordinates
                    location = self.diagram.query_point(item.api_object)
                    if location:
                        location.x = x
                        location.y = y

        # set the limits of the view
        self.set_limits(min_x, max_x, min_y, max_y)

    def expand_node_distances(self) -> None:
        """
        Expand the grid
        """
        self.apply_expansion_factor(self.expand_factor)

    def shrink_node_distances(self) -> None:
        """
        Shrink node distances
        """
        self.apply_expansion_factor(1.0 / self.expand_factor)

    def set_limits(self, min_x: int, max_x: Union[float, int], min_y: Union[float, int], max_y: int,
                   margin_factor: float = 0.1) -> None:
        """
        Set the picture limits
        :param min_x: Minimum x value of the buses location
        :param max_x: Maximum x value of the buses location
        :param min_y: Minimum y value of the buses location
        :param max_y: Maximum y value of the buses location
        :param margin_factor: factor of separation between the buses
        """
        dx = max_x - min_x
        dy = max_y - min_y
        mx = margin_factor * dx
        my = margin_factor * dy
        h = dy + 2 * my + 80
        w = dx + 2 * mx + 80
        self.diagramScene.setSceneRect(QRectF(min_x - mx, min_y - my, w, h))

    def center_nodes(self, margin_factor: float = 0.1, buses: Union[None, List[Bus]] = None):
        """
        Center the view in the nodes
        @return: Nothing
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize
        if buses is None:
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x()
                    y = item.pos().y()

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
        else:
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:

                    if item.api_object in buses:
                        x = item.pos().x()
                        y = item.pos().y()

                        max_x = max(max_x, x)
                        min_x = min(min_x, x)
                        max_y = max(max_y, y)
                        min_y = min(min_y, y)

        # set the limits of the view
        dx = max_x - min_x
        dy = max_y - min_y
        mx = margin_factor * dx
        my = margin_factor * dy
        h = dy + 2 * my + 80
        w = dx + 2 * mx + 80
        boundaries = QRectF(min_x - mx, min_y - my, w, h)

        self.diagramScene.setSceneRect(boundaries)
        self.editor_graphics_view.fitInView(boundaries, Qt.KeepAspectRatio)
        self.editor_graphics_view.scale(1.0, 1.0)

    def get_graph(self):
        """
        Get graph of the diagram (Not the circuit)
        """
        graph = nx.DiGraph()

        bus_dictionary = dict()

        for i, bus, graphic_object in self.get_buses():
            graph.add_node(i)
            bus_dictionary[bus.idtag] = i

        tuples = list()

        for dev_type in self.circuit.get_branches_types():

            points_group = self.diagram.data.get(dev_type.value, None)

            if points_group:

                for idtag, point in points_group.locations.items():
                    branch = point.api_object
                    f = bus_dictionary[branch.bus_from.idtag]
                    t = bus_dictionary[branch.bus_to.idtag]
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-3
                    tuples.append((f, t, w))

        graph.add_weighted_edges_from(tuples)

        return graph

    def auto_layout(self, sel):
        """
        Automatic layout of the nodes
        """

        nx_graph, buses_graphic_objects = self.diagram.build_graph()

        layout_algorithms_dict = dict()
        layout_algorithms_dict['circular_layout'] = nx.circular_layout
        layout_algorithms_dict['random_layout'] = nx.random_layout
        layout_algorithms_dict['shell_layout'] = nx.shell_layout
        layout_algorithms_dict['spring_layout'] = nx.spring_layout
        layout_algorithms_dict['spectral_layout'] = nx.spectral_layout
        layout_algorithms_dict['fruchterman_reingold_layout'] = nx.fruchterman_reingold_layout
        layout_algorithms_dict['kamada_kawai'] = nx.kamada_kawai_layout

        if sel == 'random_layout':
            pos = nx.random_layout(nx_graph)
        elif sel == 'spring_layout':
            pos = nx.spring_layout(nx_graph, iterations=100, scale=10)
        elif sel == 'shell_layout':
            pos = nx.shell_layout(nx_graph, scale=10)
        elif sel == 'circular_layout':
            pos = nx.circular_layout(nx_graph, scale=10)
        elif sel == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(nx_graph, scale=10)
        elif sel == 'fruchterman_reingold_layout':
            pos = nx.fruchterman_reingold_layout(nx_graph, scale=10)
        else:
            pos = nx.spring_layout(nx_graph, iterations=100, scale=10)

        # assign the positions to the graphical objects of the nodes
        for i, bus in enumerate(buses_graphic_objects):

            loc = self.diagram.query_point(bus)

            x, y = pos[i] * 500

            # apply changes to the API objects
            loc.x = x
            loc.y = y
            loc.graphic_object.set_position(x, y)

        self.center_nodes()

    def fill_xy_from_lat_lon(self,
                             destructive: bool = True,
                             factor: float = 0.01,
                             remove_offset: bool = True):
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        :param remove_offset: remove the sometimes huge offset coming from pyproj
        :return Logger object
        """

        buses_info_list = self.get_buses()

        n = len(buses_info_list)
        lon = np.zeros(n)
        lat = np.zeros(n)
        i = 0
        for idx, bus, graphic_object in buses_info_list:
            lon[i] = bus.longitude
            lat[i] = bus.latitude
            i += 1

        transformer = pyproj.Transformer.from_crs(4326, 25830, always_xy=True)

        # the longitude is more reated to x, the latitude is more related to y
        x, y = transformer.transform(xx=lon, yy=lat)
        x *= - factor
        y *= factor

        # remove the offset
        if remove_offset:
            x_min = np.min(x)
            y_max = np.max(y)
            x -= x_min + 100  # 100 is a healthy offset
            y -= y_max - 100  # 100 is a healthy offset

        # assign the values
        i = 0
        for idx, bus, graphic_object in buses_info_list:
            graphic_object.set_position(x[i], y[i])
            if destructive:
                bus.x = x[i]
                bus.y = y[i]
            i += 1

    def export(self, filename, w=1920, h=1080):
        """
        Save the grid to a png file
        """

        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.diagramScene.render(painter)
            image.save(filename)
            painter.end()

        elif extension == '.svg':
            svg_gen = QSvgGenerator()
            svg_gen.setFileName(filename)
            svg_gen.setSize(QSize(w, h))
            svg_gen.setViewBox(QRect(0, 0, w, h))
            svg_gen.setTitle("Electrical grid schematic")
            svg_gen.setDescription("An SVG drawing created by GridCal")

            painter = QPainter(svg_gen)
            self.diagramScene.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    # def add_line(self, branch: Line):
    #     """
    #     Add branch to the schematic
    #     :param branch: Branch object
    #     """
    #     terminal_from = branch.bus_from.graphic_obj.terminal
    #     terminal_to = branch.bus_to.graphic_obj.terminal
    #     graphic_obj = LineGraphicItem(fromPort=terminal_from, toPort=terminal_to, editor=self, api_object=branch)
    #     graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
    #     terminal_from.hosting_connections.append(graphic_obj)
    #     terminal_to.hosting_connections.append(graphic_obj)
    #     graphic_obj.redraw()
    #     self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    # def add_dc_line(self, branch: DcLine):
    #     """
    #     Add branch to the schematic
    #     :param branch: Branch object
    #     """
    #     terminal_from = branch.bus_from.graphic_obj.terminal
    #     terminal_to = branch.bus_to.graphic_obj.terminal
    #     graphic_obj = DcLineGraphicItem(fromPort=terminal_from, toPort=terminal_to, editor=self, api_object=branch)
    #     graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
    #     terminal_from.hosting_connections.append(graphic_obj)
    #     terminal_to.hosting_connections.append(graphic_obj)
    #     graphic_obj.redraw()
    #     self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    # def add_transformer(self, branch: Transformer2W):
    #     """
    #     Add branch to the schematic
    #     :param branch: Branch object
    #     """
    #     terminal_from = branch.bus_from.graphic_obj.terminal
    #     terminal_to = branch.bus_to.graphic_obj.terminal
    #     graphic_obj = TransformerGraphicItem(fromPort=terminal_from, toPort=terminal_to, editor=self, api_object=branch)
    #     graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
    #     terminal_from.hosting_connections.append(graphic_obj)
    #     terminal_to.hosting_connections.append(graphic_obj)
    #     graphic_obj.redraw()
    #     self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    def add_api_bus(self, bus: Bus, explode_factor: float = 1.0):
        """
        Add API bus to the diagram
        :param bus: Bus instance
        :param explode_factor: explode factor
        """
        x = int(bus.x * explode_factor)
        y = int(bus.y * explode_factor)

        # add the graphic object to the diagram view
        graphic_object = self.editor_graphics_view.add_bus(bus=bus, x=x, y=y, w=bus.w, h=bus.h)

        # add circuit pointer to the bus graphic element
        graphic_object.scene.circuit = self.circuit  # add pointer to the circuit

        # create the bus children
        graphic_object.create_children_widgets()

        # arrange the children
        graphic_object.arrange_children()

        self.update_diagram_element(device=bus,
                                    x=x,
                                    y=y,
                                    w=bus.w,
                                    h=bus.h,
                                    r=0,
                                    graphic_object=graphic_object)

        return graphic_object

    def add_api_line(self, branch: Line):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_object = LineGraphicItem(fromPort=terminal_from,
                                             toPort=terminal_to,
                                             editor=self,
                                             api_object=branch)

            graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_object)
            terminal_to.hosting_connections.append(graphic_object)
            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_dc_line(self, branch: DcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_object = DcLineGraphicItem(fromPort=terminal_from,
                                               toPort=terminal_to,
                                               editor=self,
                                               api_object=branch)

            graphic_object.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_object)
            terminal_to.hosting_connections.append(graphic_object)
            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_hvdc(self, branch: HvdcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_object = HvdcGraphicItem(fromPort=terminal_from,
                                             toPort=terminal_to,
                                             editor=self,
                                             api_object=branch)

            graphic_object.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_object)
            terminal_to.hosting_connections.append(graphic_object)
            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_vsc(self, branch: VSC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_obj = VscGraphicItem(fromPort=terminal_from,
                                         toPort=terminal_to,
                                         editor=self,
                                         api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_upfc(self, branch: UPFC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_obj = UpfcGraphicItem(fromPort=terminal_from,
                                          toPort=terminal_to,
                                          editor=self,
                                          api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_transformer(self, branch: Transformer2W):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphic_data = self.diagram.query_point(branch.bus_from)
        bus_t_graphic_data = self.diagram.query_point(branch.bus_to)

        if bus_f_graphic_data and bus_t_graphic_data:
            terminal_from = bus_f_graphic_data.graphic_object.terminal
            terminal_to = bus_t_graphic_data.graphic_object.terminal

            graphic_obj = TransformerGraphicItem(fromPort=terminal_from,
                                                 toPort=terminal_to,
                                                 editor=self,
                                                 api_object=branch)

            graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_transformer_3w(self, elm: Transformer3W):
        """
        add API branch to the Scene
        :param elm: Branch instance
        """

        tr3_graphic_object = self.editor_graphics_view.add_transformer_3w(elm=elm, x=elm.x, y=elm.y)

        bus1_graphics: BusGraphicItem = self.editor_graphics_view.editor.diagram.query_point(elm.bus1).graphic_object
        bus2_graphics: BusGraphicItem = self.editor_graphics_view.editor.diagram.query_point(elm.bus2).graphic_object
        bus3_graphics: BusGraphicItem = self.editor_graphics_view.editor.diagram.query_point(elm.bus3).graphic_object

        # add circuit pointer to the bus graphic element
        tr3_graphic_object.diagramScene.circuit = self.circuit  # add pointer to the circuit

        conn1 = WindingGraphicItem(fromPort=tr3_graphic_object.terminals[0],
                                   toPort=bus1_graphics.terminal,
                                   editor=self)
        tr3_graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

        conn2 = WindingGraphicItem(fromPort=tr3_graphic_object.terminals[1],
                                   toPort=bus2_graphics.terminal,
                                   editor=self)
        tr3_graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

        conn3 = WindingGraphicItem(fromPort=tr3_graphic_object.terminals[2],
                                   toPort=bus3_graphics.terminal,
                                   editor=self)
        tr3_graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

        tr3_graphic_object.update_conn()

        self.update_diagram_element(device=elm.idtag,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
                                    graphic_object=tr3_graphic_object)

        self.update_diagram_element(device=conn1.api_object, graphic_object=conn1)
        self.update_diagram_element(device=conn2.api_object, graphic_object=conn2)
        self.update_diagram_element(device=conn3.api_object, graphic_object=conn3)

        return tr3_graphic_object

    def convert_line_to_hvdc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to HVDC, this is the GUI way to create HVDC objects
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        hvdc = self.circuit.convert_line_to_hvdc(line)

        # add device to the schematic
        graphic_obj = self.add_api_hvdc(hvdc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line_graphic)

        self.update_diagram_element(device=hvdc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_transformer(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to Transformer
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        transformer = self.circuit.convert_line_to_transformer(line)

        # add device to the schematic
        graphic_obj = self.add_api_transformer(transformer)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line_graphic)

        self.update_diagram_element(device=transformer, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_vsc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        vsc = self.circuit.convert_line_to_vsc(line)

        # add device to the schematic
        graphic_obj = self.add_api_vsc(vsc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line_graphic)

        self.update_diagram_element(device=vsc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_upfc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        upfc = self.circuit.convert_line_to_upfc(line)

        # add device to the schematic
        graphic_obj = self.add_api_upfc(upfc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line_graphic)

        self.update_diagram_element(device=upfc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_generator_to_battery(self, gen: Generator, graphic_object: GeneratorGraphicItem):
        """
        Convert a generator to a battery
        :param gen: Generator instance
        :param graphic_object: GeneratorGraphicItem
        :return: Nothing
        """
        battery = self.circuit.convert_generator_to_battery(gen)

        bus_graphic_object: BusGraphicItem = self.diagram.query_point(gen.bus).graphic_object

        # add device to the schematic
        if bus_graphic_object is not None:
            bus_graphic_object.add_battery(battery)
        else:
            raise Exception("Bus graphics not found! this is likely a bug")

        # delete from the schematic
        graphic_object.remove(ask=False)

    def add_elements_to_schematic(self,
                                  buses: List[Bus],
                                  lines: List[Line],
                                  dc_lines: List[DcLine],
                                  transformers2w: List[Transformer2W],
                                  transformers3w: List[Transformer3W],
                                  hvdc_lines: List[HvdcLine],
                                  vsc_devices: List[VSC],
                                  upfc_devices: List[UPFC],
                                  explode_factor=1.0,
                                  prog_func: Union[Callable, None] = None,
                                  text_func: Union[Callable, None] = None):
        """
        Add a elements to the schematic scene
        :param buses: list of Bus objects
        :param lines: list of Line objects
        :param dc_lines: list of DcLine objects
        :param transformers2w: list of Transformer Objects
        :param transformers3w: list of Transformer3W Objects
        :param hvdc_lines: list of HvdcLine objects
        :param vsc_devices: list Vsc objects
        :param upfc_devices: List of UPFC devices
        :param explode_factor: factor of "explosion": Separation of the nodes factor
        :param prog_func: progress report function
        :param text_func: Text report function
        """

        # first create the buses
        if text_func is not None:
            text_func('Creating schematic buses')

        nn = len(buses)
        for i, bus in enumerate(buses):

            if not bus.is_tr_bus:  # 3w transformer buses are not represented

                if prog_func is not None:
                    prog_func((i + 1) / nn * 100.0)

                self.add_api_bus(bus, explode_factor)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(lines)
        for i, branch in enumerate(lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(dc_lines)
        for i, branch in enumerate(dc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_dc_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer devices')

        nn = len(transformers2w)
        for i, branch in enumerate(transformers2w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_transformer(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer3w devices')

        nn = len(transformers3w)
        for i, elm in enumerate(transformers3w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_transformer_3w(elm)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic HVDC devices')

        nn = len(hvdc_lines)
        for i, branch in enumerate(hvdc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_hvdc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic VSC devices')

        nn = len(vsc_devices)
        for i, branch in enumerate(vsc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_vsc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic UPFC devices')

        nn = len(upfc_devices)
        for i, branch in enumerate(upfc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_upfc(branch)

    def align_schematic(self, buses: List[Bus] = ()):
        """
        Align the scene view to the content
        :param buses: list of buses to use for alignment
        """
        # figure limits
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(buses):
            lst = buses
        else:
            lst = self.circuit.buses

        if len(lst):
            # first pass
            for bus in lst:

                location = self.diagram.query_point(bus)

                if location is not None:

                    if location.graphic_object:
                        location.graphic_object.arrange_children()
                        x = location.graphic_object.pos().x()
                        y = location.graphic_object.pos().y()

                        # compute the boundaries of the grid
                        max_x = max(max_x, x)
                        min_x = min(min_x, x)
                        max_y = max(max_y, y)
                        min_y = min(min_y, y)

            # second pass
            for bus in lst:
                location = self.diagram.query_point(bus)

                if location is not None:

                    if location.graphic_object:
                        # get the item position
                        x = location.graphic_object.pos().x()
                        y = location.graphic_object.pos().y()
                        location.x = x - min_x
                        location.y = y - max_y
                        location.graphic_object.set_position(location.x, location.y)

            # set the figure limits
            self.set_limits(0, max_x - min_x, min_y - max_y, 0)

            #  center the view
            self.center_nodes()

    def clear(self):
        """
        Clear the schematic
        """
        self.editor_graphics_view.diagram_scene.clear()

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        :return:
        """

        for key, group in self.diagram.data.items():
            for idtag, location in group.locations.items():
                if location.graphic_object is not None:
                    location.graphic_object.recolour_mode()

    def set_dark_mode(self) -> None:
        """
        Set the dark theme
        :return:
        """
        ACTIVE['color'] = Qt.white
        ACTIVE['text'] = Qt.white
        self.recolour_mode()

    def set_light_mode(self) -> None:
        """
        Set the light theme
        :return:
        """
        ACTIVE['color'] = Qt.black
        ACTIVE['text'] = Qt.black
        self.recolour_mode()

    def colour_results(self,
                       buses: List[Bus],
                       branches: List[Union[Line, DcLine, Transformer2W, Winding, UPFC, VSC]],
                       hvdc_lines: List[HvdcLine],
                       Sbus: CxVec,
                       bus_active: IntVec,
                       Sf: CxVec,
                       St: CxVec,
                       voltages: CxVec,
                       loadings: CxVec,
                       types: IntVec = None,
                       losses: CxVec = None,
                       br_active: IntVec = None,
                       hvdc_Pf: Vec = None,
                       hvdc_Pt: Vec = None,
                       hvdc_losses: Vec = None,
                       hvdc_loading: Vec = None,
                       hvdc_active: IntVec = None,
                       loading_label: str = 'loading',
                       ma: Vec = None,
                       theta: Vec = None,
                       Beq: Vec = None,
                       use_flow_based_width: bool = False,
                       min_branch_width: int = 5,
                       max_branch_width=5,
                       min_bus_width=20,
                       max_bus_width=20,
                       cmap: palettes.Colormaps = None):
        """
        Color objects based on the results passed
        :param buses: list of matching bus objects
        :param branches: list of Branches without HVDC
        :param hvdc_lines: list of HVDC lines
        :param Sbus: Buses power (MVA)
        :param bus_active: Bus active status
        :param Sf: Branches power from the "from" bus (MVA)
        :param St: Branches power from the "to" bus (MVA)
        :param voltages: Buses voltage
        :param loadings: Branches load (%)
        :param types: Buses type [PQ: 1, PV: 2, REF: 3, NONE: 4, STO_DISPATCH: 5, PVB: 6]
        :param losses: Branches losses [%]
        :param br_active: Branches active status
        :param hvdc_Pf: HVDC branch flows "from" [MW]
        :param hvdc_Pt: HVDC branch flows "to" [MW]
        :param hvdc_losses: HVDC branch losses [MW]
        :param hvdc_loading: HVDC Branch loading [%]
        :param hvdc_active: HVDC Branch status
        :param loading_label: String saling whatever the loading label means
        :param ma: branch phase shift angle (rad)
        :param theta: branch tap module (p.u.)
        :param Beq: Branch equivanet susceptance (p.u.)
        :param use_flow_based_width: use branch width based on the actual flow?
        :param min_branch_width: Minimum branch width [px]
        :param max_branch_width: Maximum branch width [px]
        :param min_bus_width: Minimum bus width [px]
        :param max_bus_width: Maximum bus width [px]
        :param cmap: Color map [palettes.Colormaps]
        """

        # color nodes
        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = np.abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng

        if Sbus is not None:
            if len(Sbus) > 0:
                Pabs = np.abs(Sbus)
                mx = Pabs.max()
                if mx != 0.0:
                    Pnorm = Pabs / mx
                else:
                    Pnorm = np.zeros(len(buses))
            else:
                Pnorm = np.zeros(len(buses))
        else:
            Pnorm = np.zeros(len(buses))

        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()

        '''
        class BusMode(Enum):
        PQ = 1,
        PV = 2,
        REF = 3,
        NONE = 4,
        STO_DISPATCH = 5
        PVB = 6
        '''

        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage', 'P', 'PQV']
        max_flow = 1

        for i, bus in enumerate(buses):

            location = self.diagram.query_point(bus)

            if location:

                if location.graphic_object:

                    graphic_object: BusGraphicItem = location.graphic_object

                    if bus_active[i]:
                        a = 255
                        if cmap == palettes.Colormaps.Green2Red:
                            b, g, r = palettes.green_to_red_bgr(vnorm[i])

                        elif cmap == palettes.Colormaps.Heatmap:
                            b, g, r = palettes.heatmap_palette_bgr(vnorm[i])

                        elif cmap == palettes.Colormaps.TSO:
                            b, g, r = palettes.tso_substation_palette_bgr(vnorm[i])

                        else:
                            r, g, b, a = voltage_cmap(vnorm[i])
                            r *= 255
                            g *= 255
                            b *= 255
                            a *= 255

                        graphic_object.set_tile_color(QColor(r, g, b, a))

                        tooltip = str(i) + ': ' + bus.name
                        if types is not None:
                            tooltip += ': ' + bus_types[types[i]]
                        tooltip += '\n'

                        tooltip += "%-10s %10.4f < %10.4fº [p.u.]\n" % ("V", vabs[i], vang[i])
                        tooltip += "%-10s %10.4f < %10.4fº [kV]\n" % ("V", vabs[i] * bus.Vnom, vang[i])

                        if Sbus is not None:
                            tooltip += "%-10s %10.4f [MW]\n" % ("P", Sbus[i].real)
                            tooltip += "%-10s %10.4f [MVAr]\n" % ("Q", Sbus[i].imag)

                        graphic_object.setToolTip(tooltip)

                        if use_flow_based_width:
                            h = int(np.floor(min_bus_width + Pnorm[i] * (max_bus_width - min_bus_width)))
                            graphic_object.change_size(graphic_object.w, h)

                    else:
                        graphic_object.set_tile_color(Qt.gray)

                else:
                    print("Bus {0} {1} has no graphic object!!".format(bus.name, bus.idtag))

        # color Branches
        if Sf is not None:
            if len(Sf) > 0:
                lnorm = np.abs(loadings)
                lnorm[lnorm == np.inf] = 0
                Sfabs = np.abs(Sf)
                max_flow = Sfabs.max()

                if hvdc_Pf is not None:
                    if len(hvdc_Pf) > 0:
                        max_flow = max(max_flow, np.abs(hvdc_Pf).max())

                if max_flow != 0:
                    Sfnorm = Sfabs / max_flow
                else:
                    Sfnorm = Sfabs

                for i, branch in enumerate(branches):

                    location = self.diagram.query_point(branch)

                    if location:

                        if location.graphic_object:

                            graphic_object: LineGraphicItem = location.graphic_object

                            if br_active[i]:

                                if use_flow_based_width:
                                    w = int(
                                        np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                                else:
                                    w = graphic_object.pen_width

                                if branch.active:
                                    style = Qt.SolidLine

                                    a = 255
                                    if cmap == palettes.Colormaps.Green2Red:
                                        b, g, r = palettes.green_to_red_bgr(lnorm[i])

                                    elif cmap == palettes.Colormaps.Heatmap:
                                        b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                                    elif cmap == palettes.Colormaps.TSO:
                                        b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(),
                                                                                lnorm[i])

                                    else:
                                        r, g, b, a = loading_cmap(lnorm[i])
                                        r *= 255
                                        g *= 255
                                        b *= 255
                                        a *= 255

                                    color = QColor(r, g, b, a)
                                else:
                                    style = Qt.DashLine
                                    color = Qt.gray

                                tooltip = str(i) + ': ' + branch.name
                                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'

                                tooltip += '\nPower (from):\t' + "{:10.4f}".format(Sf[i]) + ' [MVA]'

                                if St is not None:
                                    tooltip += '\nPower (to):\t' + "{:10.4f}".format(St[i]) + ' [MVA]'

                                if losses is not None:
                                    tooltip += '\nLosses:\t\t' + "{:10.4f}".format(losses[i]) + ' [MVA]'

                                if branch.device_type == DeviceType.Transformer2WDevice:
                                    if ma is not None:
                                        tooltip += '\ntap module:\t' + "{:10.4f}".format(ma[i])

                                    if theta is not None:
                                        tooltip += '\ntap angle:\t' + "{:10.4f}".format(theta[i]) + ' rad'

                                if branch.device_type == DeviceType.VscDevice:
                                    if ma is not None:
                                        tooltip += '\ntap module:\t' + "{:10.4f}".format(ma[i])

                                    if theta is not None:
                                        tooltip += '\nfiring angle:\t' + "{:10.4f}".format(theta[i]) + ' rad'

                                    if Beq is not None:
                                        tooltip += '\nBeq:\t' + "{:10.4f}".format(Beq[i])

                                graphic_object.setToolTipText(tooltip)
                                graphic_object.set_colour(color, w, style)

                                if hasattr(location.graphic_object, 'set_arrows_with_power'):
                                    location.graphic_object.set_arrows_with_power(Sf=Sf[i] if Sf is not None else None,
                                                                                  St=St[i] if St is not None else None)
                            else:
                                w = graphic_object.pen_width
                                style = Qt.DashLine
                                color = Qt.gray
                                graphic_object.set_pen(QPen(color, w, style))
                        else:
                            print("Branch {0} {1} has no graphic object!!".format(branch.name, branch.idtag))

        if hvdc_Pf is not None:

            hvdc_sending_power_norm = np.abs(hvdc_Pf) / (max_flow + 1e-20)

            for i, elm in enumerate(hvdc_lines):

                location = self.diagram.query_point(elm)

                if location:

                    if location.graphic_object:

                        graphic_object: HvdcGraphicItem = location.graphic_object

                        if hvdc_active[i]:

                            if use_flow_based_width:
                                w = int(np.floor(
                                    min_branch_width + hvdc_sending_power_norm[i] * (
                                            max_branch_width - min_branch_width)))
                            else:
                                w = graphic_object.pen_width

                            if elm.active:
                                style = Qt.SolidLine

                                a = 1
                                if cmap == palettes.Colormaps.Green2Red:
                                    b, g, r = palettes.green_to_red_bgr(abs(hvdc_loading[i]))

                                elif cmap == palettes.Colormaps.Heatmap:
                                    b, g, r = palettes.heatmap_palette_bgr(abs(hvdc_loading[i]))

                                elif cmap == palettes.Colormaps.TSO:
                                    b, g, r = palettes.tso_line_palette_bgr(elm.get_max_bus_nominal_voltage(),
                                                                            abs(hvdc_loading[i]))

                                else:
                                    r, g, b, a = loading_cmap(abs(hvdc_loading[i]))
                                    r *= 255
                                    g *= 255
                                    b *= 255
                                    a *= 255

                                color = QColor(r, g, b, a)
                            else:
                                style = Qt.DashLine
                                color = Qt.gray

                            tooltip = str(i) + ': ' + elm.name
                            tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(
                                abs(hvdc_loading[i]) * 100) + ' [%]'

                            tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'

                            if hvdc_losses is not None:
                                tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_Pt[i]) + ' [MW]'
                                tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                                graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=hvdc_Pt[i])
                            else:
                                graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=-hvdc_Pf[i])

                            graphic_object.setToolTipText(tooltip)
                            graphic_object.set_colour(color, w, style)
                        else:
                            w = graphic_object.pen_width
                            style = Qt.DashLine
                            color = Qt.gray
                            graphic_object.set_pen(QPen(color, w, style))
                    else:
                        print("HVDC line {0} {1} has no graphic object!!".format(elm.name, elm.idtag))

    def get_selection_api_objects(self) -> List[EditableDevice]:
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return [e.api_object for e in self.diagramScene.selectedItems()]

    def get_selection_diagram(self) -> BusBranchDiagram:
        """
        Get a BusBranchDiagram of the current selection
        :return: BusBranchDiagram
        """
        diagram = BusBranchDiagram(name="Selection diagram")

        # first pass (only buses)
        bus_dict = dict()
        for item in self.diagramScene.selectedItems():
            if isinstance(item, BusGraphicItem):
                # check that the bus is in the original diagram
                location = self.diagram.query_point(item.api_object)

                if location:
                    diagram.set_point(device=item.api_object, location=location)
                    bus_dict[item.api_object.idtag] = item
                else:
                    raise Exception('Item was selected but was not registered!')

        # second pass (Branches, and include their not selected buses)
        for item in self.diagramScene.selectedItems():
            if not isinstance(item, BusGraphicItem):

                # add the element
                rect = item.boundingRect()
                diagram.set_point(device=item.api_object,
                                  location=GraphicLocation(x=rect.x(),
                                                           y=rect.y(),
                                                           h=rect.height(),
                                                           w=rect.width(),
                                                           r=item.rotation(),
                                                           api_object=item.api_object))

                if hasattr(item.api_object, 'bus_from'):  # if the element is a branch ...

                    # get the api buses from and to
                    bus_from = item.api_object.bus_from
                    bus_to = item.api_object.bus_to

                    for bus in [bus_from, bus_to]:

                        # check that the bus is in the original diagram
                        location = self.diagram.query_point(bus)

                        if location and (bus.idtag not in bus_dict):
                            # if the bus was not added in the first
                            # pass and is in the original diagram, add it now
                            diagram.set_point(device=bus, location=location)
                            bus_dict[bus.idtag] = location.graphic_object

        return diagram

    def try_to_fix_buses_location(self, buses_selection: List[Tuple[int, Bus, BusGraphicItem]]):
        """
        Try to fix the location of the null-location buses
        :param buses_selection: list of tuples index, bus object, graphic_object
        :return: indices of the corrected buses
        """
        delta = 1e20
        locations_cache = dict()

        while delta > 10:

            A = self.circuit.get_adjacent_matrix()

            for k, bus, graphic_object in buses_selection:

                idx = list(self.circuit.get_adjacent_buses(A, k))

                # remove the elements already in the selection
                for i in range(len(idx) - 1, 0, -1):
                    if k == idx[i]:
                        idx.pop(i)

                x_arr = list()
                y_arr = list()
                for i in idx:

                    # try to get the location from the cache
                    loc_i = locations_cache.get(self.circuit.buses[i], None)

                    if loc_i is None:
                        # search and store
                        loc_i = self.diagram.query_point(self.circuit.buses[i])
                        locations_cache[self.circuit.buses[i]] = loc_i

                    x_arr.append(loc_i.x)
                    y_arr.append(loc_i.y)

                x_m = np.mean(x_arr)
                y_m = np.mean(y_arr)

                delta_i = np.sqrt((graphic_object.x() - x_m) ** 2 + (graphic_object.y() - y_m) ** 2)

                if delta_i < delta:
                    delta = delta_i

                self.update_diagram_element(device=bus,
                                            x=x_m,
                                            y=y_m,
                                            w=graphic_object.w,
                                            h=graphic_object.h,
                                            r=0,
                                            graphic_object=graphic_object)
                graphic_object.set_position(x=x_m, y=y_m)

        return

    def get_boundaries(self):
        """
        Get the graphic representation boundaries
        :return: min_x, max_x, min_y, max_y
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        # shrink selection only
        for i, bus, graphic_object in self.get_buses():
            x = graphic_object.x()
            y = graphic_object.y()
            max_x = max(max_x, x)
            min_x = min(min_x, x)
            max_y = max(max_y, y)
            min_y = min(min_y, y)

        return min_x, max_x, min_y, max_y

    def average_separation(self):
        """
        Average separation of the buses
        :return: average separation
        """
        separation = 0.0
        branch_lists = self.get_branch_lists()
        n = 0
        for branch_lst in branch_lists:
            for branch in branch_lst:
                s = np.sqrt((branch.bus_from.x - branch.bus_to.x) ** 2 + (branch.bus_from.y - branch.bus_to.y) ** 2)
                separation += s
                n += 1
        return separation / n


def generate_bus_branch_diagram(buses: List[Bus],
                                lines: List[Line],
                                dc_lines: List[DcLine],
                                transformers2w: List[Transformer2W],
                                transformers3w: List[Transformer3W],
                                hvdc_lines: List[HvdcLine],
                                vsc_devices: List[VSC],
                                upfc_devices: List[UPFC],
                                explode_factor=1.0,
                                prog_func: Union[Callable, None] = None,
                                text_func: Union[Callable, None] = None,
                                name='Bus branch diagram') -> BusBranchDiagram:
    """
    Add a elements to the schematic scene
    :param buses: list of Bus objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param transformers2w: list of Transformer Objects
    :param transformers3w: list of Transformer3W Objects
    :param hvdc_lines: list of HvdcLine objects
    :param vsc_devices: list Vsc objects
    :param upfc_devices: List of UPFC devices
    :param explode_factor: factor of "explosion": Separation of the nodes factor
    :param prog_func: progress report function
    :param text_func: Text report function
    :param name: name of the diagram
    """

    diagram = BusBranchDiagram(name=name)

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(buses)
    for i, bus in enumerate(buses):

        if not bus.is_tr_bus:  # 3w transformer buses are not represented

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            # correct possible nonsense
            if np.isnan(bus.y):
                bus.y = 0.0
            if np.isnan(bus.x):
                bus.x = 0.0

            x = int(bus.x * explode_factor)
            y = int(bus.y * explode_factor)
            diagram.set_point(device=bus, location=GraphicLocation(x=x, y=y, h=bus.h, w=bus.w))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(lines)
    for i, branch in enumerate(lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_line(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(dc_lines)
    for i, branch in enumerate(dc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_dc_line(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic transformer devices')

    nn = len(transformers2w)
    for i, branch in enumerate(transformers2w):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_transformer(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic transformer3w devices')

    nn = len(transformers3w)
    for i, elm in enumerate(transformers3w):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # elm.graphic_obj = self.add_api_transformer_3w(elm, explode_factor, filter_with_diagram)
        x = int(elm.x * explode_factor)
        y = int(elm.y * explode_factor)
        diagram.set_point(device=elm, location=GraphicLocation(x=x, y=y))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic HVDC devices')

    nn = len(hvdc_lines)
    for i, branch in enumerate(hvdc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_hvdc(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic VSC devices')

    nn = len(vsc_devices)
    for i, branch in enumerate(vsc_devices):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_vsc(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic UPFC devices')

    nn = len(upfc_devices)
    for i, branch in enumerate(upfc_devices):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_upfc(branch)
        diagram.set_point(device=branch, location=GraphicLocation())

    return diagram


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = BusBranchEditorWidget(circuit=MultiCircuit(),
                                   diagram=BusBranchDiagram(),
                                   default_bus_voltage=10.0)

    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
