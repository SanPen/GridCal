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
from typing import List, Dict, Union
from collections.abc import Callable
import networkx as nx

from PySide6.QtCore import Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray, \
    QDataStream, QModelIndex
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen, \
    QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsView, QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame, \
    QSplitter, QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsSceneMouseEvent
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
from GridCalEngine.Core.Devices.Branches.transformer3w import Transformer3W
from GridCalEngine.Core.Devices.Injections.generator import Generator
from GridCalEngine.Core.Devices.enumerations import DeviceType
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Core.Devices.Diagrams.bus_branch_diagram import BusBranchDiagram
from GridCalEngine.Core.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.basic_structures import Vec, CxVec, IntVec

from GridCal.Gui.GridEditorWidget.terminal_item import TerminalItem
from GridCal.Gui.GridEditorWidget.bus_graphics import BusGraphicItem
from GridCal.Gui.GridEditorWidget.line_graphics import LineGraphicItem
from GridCal.Gui.GridEditorWidget.winding_graphics import WindingGraphicItem
from GridCal.Gui.GridEditorWidget.dc_line_graphics import DcLineGraphicItem
from GridCal.Gui.GridEditorWidget.transformer2w_graphics import TransformerGraphicItem
from GridCal.Gui.GridEditorWidget.hvdc_graphics import HvdcGraphicItem
from GridCal.Gui.GridEditorWidget.vsc_graphics import VscGraphicItem
from GridCal.Gui.GridEditorWidget.upfc_graphics import UpfcGraphicItem
from GridCal.Gui.GridEditorWidget.transformer3w_graphics import Transformer3WGraphicItem
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


class DiagramScene(QGraphicsScene):
    """
    DiagramScene
    """

    def __init__(self, parent: "GridEditorWidget", circuit: MultiCircuit):
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

    def plot_branch(self, i, api_object):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: API object
        :return:
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

    def plot_hvdc_branch(self, i, api_object):
        """

        :param api_object:
        :return:
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

    def __init__(self, diagram_scene: DiagramScene, editor: "GridEditorWidget"):
        """
        Editor where the diagram is displayed
        @param diagram_scene: DiagramScene object
        @param parent:
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
            graphic_obj = None
            bus_data = toQBytesArray('Bus')
            tr3w_data = toQBytesArray('3W-Transformer')

            point0 = self.mapToScene(event.position().x(), event.position().y())
            x0 = point0.x()
            y0 = point0.y()

            if bus_data == obj_type:
                name = 'Bus ' + str(len(self.diagram_scene.circuit.buses))

                obj = Bus(name=name,
                          area=self.diagram_scene.circuit.areas[0],
                          zone=self.diagram_scene.circuit.zones[0],
                          substation=self.diagram_scene.circuit.substations[0],
                          country=self.diagram_scene.circuit.countries[0])

                graphic_obj = self.add_bus(bus=obj, x=x0, y=y0, h=20, w=80)
                obj.graphic_obj = graphic_obj

                # weird but it's the only way to have graphical-API communication
                self.diagram_scene.circuit.add_bus(obj)

                # add to the diagram list
                self.editor.update_diagram_element(device=obj, x=x0, y=y0,
                                                   w=graphic_obj.w, h=graphic_obj.h, r=0,
                                                   graphic_object=graphic_obj)

            elif tr3w_data == obj_type:
                name = "Transformer 3-windings" + str(len(self.diagram_scene.circuit.transformers3w))
                obj = Transformer3W(name=name)
                graphic_obj = self.add_transformer_3w(elm=obj, x=x0, y=y0)
                obj.graphic_obj = graphic_obj

                # weird but it's the only way to have graphical-API communication
                self.diagram_scene.circuit.add_transformer3w(obj)

                # add to the diagram list
                self.editor.update_diagram_element(device=obj, x=x0, y=y0, w=graphic_obj.w, h=graphic_obj.h, r=0,
                                                   graphic_object=graphic_obj)

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

        graphic_obj = BusGraphicItem(scene=self.scene(), editor=self.editor, bus=bus, x=x, y=y, h=h, w=w)
        self.diagram_scene.addItem(graphic_obj)
        return graphic_obj

    def add_transformer_3w(self, elm: Transformer3W, x: int, y: int) -> Transformer3WGraphicItem:
        """

        :param elm: Transformer3W
        :param x: x coordinate
        :param y: y coordinate
        :return: Transformer3WGraphicItem
        """
        graphic_obj = Transformer3WGraphicItem(diagramScene=self.scene(), editor=self.editor, elm=elm)
        graphic_obj.setPos(QPoint(x, y))
        self.diagram_scene.addItem(graphic_obj)
        return graphic_obj


class GridEditorWidget(QSplitter):
    """
    GridEditorWidget
    """

    def __init__(self, circuit: MultiCircuit, diagram: Union[BusBranchDiagram, None]):
        """
        Creates the Diagram Editor
        Args:
            circuit: Circuit that is handling
        """
        QSplitter.__init__(self)

        # store a reference to the multi circuit instance
        self.circuit: MultiCircuit = circuit

        # diagram to store the objects locations
        self.diagram: BusBranchDiagram = diagram

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

        self.started_branch = None

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
                    graphic_obj = self.editor_graphics_view.add_bus(bus=location.api_object,
                                                                    x=location.x,
                                                                    y=location.y,
                                                                    h=location.h,
                                                                    w=location.w)

                    # add circuit pointer to the bus graphic element
                    graphic_obj.scene.circuit = self.circuit  # add pointer to the circuit

                    # create the bus children
                    graphic_obj.create_children_widgets()

                    graphic_obj.change_size(h=location.h,
                                            w=location.w)

                    # add buses refference for later
                    bus_dict[idtag] = graphic_obj
                    # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                    points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.Transformer3WDevice.value:

                for idtag, location in points_group.locations.items():
                    elm: Transformer3W = location.api_object

                    graphic_obj = self.editor_graphics_view.add_transformer_3w(elm=elm,
                                                                               x=location.x,
                                                                               y=location.y)

                    # add circuit pointer to the bus graphic element
                    graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit

                    conn1 = WindingGraphicItem(fromPort=graphic_obj.terminals[0],
                                               toPort=elm.bus1.graphic_obj.terminal,
                                               diagramScene=self.diagramScene)

                    graphic_obj.set_connection(i=0, bus=elm.bus1, conn=conn1)

                    conn2 = WindingGraphicItem(fromPort=graphic_obj.terminals[1],
                                               toPort=elm.bus2.graphic_obj.terminal,
                                               diagramScene=self.diagramScene)
                    graphic_obj.set_connection(i=1, bus=elm.bus2, conn=conn2)

                    conn3 = WindingGraphicItem(fromPort=graphic_obj.terminals[2],
                                               toPort=elm.bus3.graphic_obj.terminal,
                                               diagramScene=self.diagramScene)
                    graphic_obj.set_connection(i=2, bus=elm.bus3, conn=conn3)

                    graphic_obj.set_position(x=location.x,
                                             y=location.y)

                    graphic_obj.change_size(h=location.h,
                                            w=location.w)

                    graphic_obj.update_conn()
                    # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                    points_group.locations[idtag].graphic_object = graphic_obj

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

                        graphic_obj = LineGraphicItem(fromPort=terminal_from,
                                                      toPort=terminal_to,
                                                      diagramScene=self.diagramScene,
                                                      api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.DCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: DcLine = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_obj = DcLineGraphicItem(fromPort=terminal_from,
                                                        toPort=terminal_to,
                                                        diagramScene=self.diagramScene,
                                                        api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.HVDCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: HvdcLine = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_obj = HvdcGraphicItem(fromPort=terminal_from,
                                                      toPort=terminal_to,
                                                      diagramScene=self.diagramScene,
                                                      api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.VscDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: VSC = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_obj = VscGraphicItem(fromPort=terminal_from,
                                                     toPort=terminal_to,
                                                     diagramScene=self.diagramScene,
                                                     api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.UpfcDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: UPFC = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_obj = UpfcGraphicItem(fromPort=terminal_from,
                                                      toPort=terminal_to,
                                                      diagramScene=self.diagramScene,
                                                      api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

            elif category == DeviceType.Transformer2WDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Transformer2W = location.api_object
                    bus_f_graphic_obj = bus_dict.get(branch.bus_from.idtag, None)
                    bus_t_graphic_obj = bus_dict.get(branch.bus_to.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_obj = TransformerGraphicItem(fromPort=terminal_from,
                                                             toPort=terminal_to,
                                                             diagramScene=self.diagramScene,
                                                             api_object=branch)

                        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
                        terminal_from.hosting_connections.append(graphic_obj)
                        terminal_to.hosting_connections.append(graphic_obj)
                        graphic_obj.redraw()
                        # location.graphic_object = graphic_obj  # locations is a deep copy (WTF!!!?)
                        points_group.locations[idtag].graphic_object = graphic_obj

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
        self.diagram.delete_device(device=device)

    def start_connection(self, port: TerminalItem):
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.started_branch = LineGraphicItem(fromPort=port, toPort=None, diagramScene=self.diagramScene)
        self.started_branch.bus_from = port.parent
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

                        if isinstance(self.started_branch.bus_from.api_object, Bus) and \
                                isinstance(self.started_branch.bus_to.api_object, Bus):

                            if self.started_branch.bus_from.api_object.is_dc != self.started_branch.bus_to.api_object.is_dc:
                                # different DC status -> VSC

                                name = 'VSC ' + str(len(self.circuit.vsc_devices) + 1)
                                obj = VSC(bus_from=self.started_branch.bus_from.api_object,
                                          bus_to=self.started_branch.bus_to.api_object,
                                          name=name)

                                graphic_obj = VscGraphicItem(fromPort=self.started_branch.fromPort,
                                                             toPort=self.started_branch.toPort,
                                                             diagramScene=self.diagramScene,
                                                             api_object=obj)
                                self.update_diagram_element(device=obj, graphic_object=graphic_obj)

                            elif self.started_branch.bus_from.api_object.is_dc and self.started_branch.bus_to.api_object.is_dc:
                                # both buses are DC

                                name = 'Dc line ' + str(len(self.circuit.dc_lines) + 1)
                                obj = DcLine(bus_from=self.started_branch.bus_from.api_object,
                                             bus_to=self.started_branch.bus_to.api_object,
                                             name=name)

                                graphic_obj = DcLineGraphicItem(fromPort=self.started_branch.fromPort,
                                                                toPort=self.started_branch.toPort,
                                                                diagramScene=self.diagramScene,
                                                                api_object=obj)
                                self.update_diagram_element(device=obj, graphic_object=graphic_obj)

                            else:
                                # Same DC status -> line / trafo
                                v1 = self.started_branch.bus_from.api_object.Vnom
                                v2 = self.started_branch.bus_to.api_object.Vnom

                                if abs(v1 - v2) > 1.0:
                                    name = 'Transformer ' + str(len(self.circuit.transformers2w) + 1)
                                    obj = Transformer2W(bus_from=self.started_branch.bus_from.api_object,
                                                        bus_to=self.started_branch.bus_to.api_object,
                                                        name=name)

                                    graphic_obj = TransformerGraphicItem(fromPort=self.started_branch.fromPort,
                                                                         toPort=self.started_branch.toPort,
                                                                         diagramScene=self.diagramScene,
                                                                         api_object=obj)
                                    self.update_diagram_element(device=obj, graphic_object=graphic_obj)

                                else:
                                    name = 'Line ' + str(len(self.circuit.lines) + 1)
                                    obj = Line(bus_from=self.started_branch.bus_from.api_object,
                                               bus_to=self.started_branch.bus_to.api_object,
                                               name=name)

                                    graphic_obj = LineGraphicItem(fromPort=self.started_branch.fromPort,
                                                                  toPort=self.started_branch.toPort,
                                                                  diagramScene=self.diagramScene,
                                                                  api_object=obj)
                                    self.update_diagram_element(device=obj, graphic_object=graphic_obj)

                            # add the new object to the circuit
                            self.circuit.add_branch(obj)

                            # update the connection placement
                            graphic_obj.fromPort.update()
                            graphic_obj.toPort.update()

                            # set the connection placement
                            graphic_obj.setZValue(-1)

                        elif isinstance(self.started_branch.bus_from.api_object, Transformer3W):

                            obj = self.started_branch.bus_from.api_object

                            if isinstance(self.started_branch.bus_to.api_object, Bus):
                                # if the bus "from" is the TR3W, the "to" is the bus
                                bus = self.started_branch.bus_to.api_object
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = obj.graphic_obj.get_connection_winding(self.started_branch.fromPort,
                                                                       self.started_branch.toPort)

                            if obj.graphic_obj.connection_lines[i] is None:
                                conn = WindingGraphicItem(fromPort=self.started_branch.fromPort,
                                                          toPort=self.started_branch.toPort,
                                                          diagramScene=self.diagramScene)

                                obj.graphic_obj.set_connection(i, bus, conn)
                                self.started_branch.fromPort.update()
                                self.started_branch.toPort.update()
                                obj.graphic_obj.update_conn()
                                self.update_diagram_element(device=obj, graphic_object=obj.graphic_obj)

                        elif isinstance(self.started_branch.bus_to.api_object, Transformer3W):

                            obj = self.started_branch.bus_to.api_object

                            if isinstance(self.started_branch.bus_from.api_object, Bus):
                                # if the bus "to" is the TR3W, the "from" is the bus
                                bus = self.started_branch.bus_from.api_object
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = obj.graphic_obj.get_connection_winding(self.started_branch.fromPort,
                                                                       self.started_branch.toPort)

                            if obj.graphic_obj.connection_lines[i] is None:
                                conn = WindingGraphicItem(fromPort=self.started_branch.fromPort,
                                                          toPort=self.started_branch.toPort,
                                                          diagramScene=self.diagramScene)

                                obj.graphic_obj.set_connection(i, bus, conn)
                                self.started_branch.fromPort.update()
                                self.started_branch.toPort.update()
                                obj.graphic_obj.update_conn()
                                self.update_diagram_element(device=obj, graphic_object=obj.graphic_obj)

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

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        if self.circuit.graph is None:
            self.circuit.build_graph()

        pos = nx.spectral_layout(self.circuit.graph, scale=2, weight='weight')

        pos = nx.fruchterman_reingold_layout(self.circuit.graph, dim=2,
                                             k=None, pos=pos, fixed=None, iterations=500,
                                             weight='weight', scale=20.0, center=None)

        # assign the positions to the graphical objects of the nodes
        for i, bus in enumerate(self.circuit.buses):
            location = self.diagram.query_point(bus)

            if location:
                x, y = pos[i] * 500

                if location.graphic_object:
                    location.graphic_object.setPos(QPoint(x, y))

                # apply changes to the API objects
                location.x = x
                location.y = y

        self.center_nodes()

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

    def add_line(self, branch: Line):
        """
        Add branch to the schematic
        :param branch: Branch object
        """
        terminal_from = branch.bus_from.graphic_obj.terminal
        terminal_to = branch.bus_to.graphic_obj.terminal
        graphic_obj = LineGraphicItem(terminal_from, terminal_to, self.diagramScene, api_object=branch)
        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
        terminal_from.hosting_connections.append(graphic_obj)
        terminal_to.hosting_connections.append(graphic_obj)
        graphic_obj.redraw()
        self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    def add_dc_line(self, branch: DcLine):
        """
        Add branch to the schematic
        :param branch: Branch object
        """
        terminal_from = branch.bus_from.graphic_obj.terminal
        terminal_to = branch.bus_to.graphic_obj.terminal
        graphic_obj = DcLineGraphicItem(terminal_from, terminal_to, self.diagramScene, api_object=branch)
        graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
        terminal_from.hosting_connections.append(graphic_obj)
        terminal_to.hosting_connections.append(graphic_obj)
        graphic_obj.redraw()
        self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    def add_transformer(self, branch: Transformer2W):
        """
        Add branch to the schematic
        :param branch: Branch object
        """
        terminal_from = branch.bus_from.graphic_obj.terminal
        terminal_to = branch.bus_to.graphic_obj.terminal
        graphic_obj = TransformerGraphicItem(terminal_from, terminal_to, self.diagramScene, api_object=branch)
        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
        terminal_from.hosting_connections.append(graphic_obj)
        terminal_to.hosting_connections.append(graphic_obj)
        graphic_obj.redraw()
        self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)

    def add_api_bus(self, bus: Bus, explode_factor: float = 1.0):
        """
        Add API bus to the diagram
        :param bus: Bus instance
        :param explode_factor: explode factor
        """
        x = int(bus.x * explode_factor)
        y = int(bus.y * explode_factor)

        # add the graphic object to the diagram view
        graphic_obj = self.editor_graphics_view.add_bus(bus=bus, x=x, y=y, w=bus.w, h=bus.h)

        # add circuit pointer to the bus graphic element
        graphic_obj.scene.circuit = self.circuit  # add pointer to the circuit

        # create the bus children
        graphic_obj.create_children_widgets()

        # arrange the children
        graphic_obj.arrange_children()

        self.update_diagram_element(device=bus,
                                    x=x,
                                    y=y,
                                    w=bus.w,
                                    h=bus.h,
                                    r=0,
                                    graphic_object=graphic_obj)

        return graphic_obj

    def add_api_line(self, branch: Line):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = LineGraphicItem(fromPort=terminal_from,
                                          toPort=terminal_to,
                                          diagramScene=self.diagramScene,
                                          api_object=branch)

            graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_dc_line(self, branch: DcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = DcLineGraphicItem(fromPort=terminal_from,
                                            toPort=terminal_to,
                                            diagramScene=self.diagramScene,
                                            api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_hvdc(self, branch: HvdcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = HvdcGraphicItem(fromPort=terminal_from,
                                          toPort=terminal_to,
                                          diagramScene=self.diagramScene,
                                          api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_vsc(self, branch: VSC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = VscGraphicItem(fromPort=terminal_from,
                                         toPort=terminal_to,
                                         diagramScene=self.diagramScene,
                                         api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_upfc(self, branch: UPFC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = UpfcGraphicItem(fromPort=terminal_from,
                                          toPort=terminal_to,
                                          diagramScene=self.diagramScene,
                                          api_object=branch)

            graphic_obj.diagramScene.grid = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_transformer(self, branch: Transformer2W):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        if branch.bus_from.graphic_obj and branch.bus_to.graphic_obj:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal

            graphic_obj = TransformerGraphicItem(fromPort=terminal_from,
                                                 toPort=terminal_to,
                                                 diagramScene=self.diagramScene,
                                                 api_object=branch)

            graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
            return graphic_obj
        else:
            return None

    def add_api_transformer_3w(self, elm: Transformer3W, explode_factor=1.0):
        """
        add API branch to the Scene
        :param elm: Branch instance
        :param explode_factor: explode factor
        """

        graphic_obj = self.editor_graphics_view.add_transformer_3w(elm=elm, x=elm.x, y=elm.y)

        # add circuit pointer to the bus graphic element
        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit

        conn1 = WindingGraphicItem(fromPort=graphic_obj.terminals[0],
                                   toPort=elm.bus1.graphic_obj.terminal,
                                   diagramScene=self.diagramScene)
        graphic_obj.set_connection(i=0, bus=elm.bus1, conn=conn1)

        conn2 = WindingGraphicItem(fromPort=graphic_obj.terminals[1],
                                   toPort=elm.bus2.graphic_obj.terminal,
                                   diagramScene=self.diagramScene)
        graphic_obj.set_connection(i=1, bus=elm.bus2, conn=conn2)

        conn3 = WindingGraphicItem(fromPort=graphic_obj.terminals[2],
                                   toPort=elm.bus3.graphic_obj.terminal,
                                   diagramScene=self.diagramScene)
        graphic_obj.set_connection(i=2, bus=elm.bus3, conn=conn3)

        graphic_obj.update_conn()

        self.update_diagram_element(device=elm.idtag,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
                                    graphic_object=graphic_obj)

        return graphic_obj

    def convert_line_to_hvdc(self, line: Line):
        """
        Convert a line to HVDC, this is the GUI way to create HVDC objects
        :param line: Line instance
        :return: Nothing
        """
        hvdc = self.circuit.convert_line_to_hvdc(line)

        # add device to the schematic
        graphic_obj = self.add_api_hvdc(hvdc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line.graphic_obj)

        self.update_diagram_element(device=hvdc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_transformer(self, line: Line):
        """
        Convert a line to Transformer
        :param line: Line instance
        :return: Nothing
        """
        transformer = self.circuit.convert_line_to_transformer(line)

        # add device to the schematic
        graphic_obj = self.add_api_transformer(transformer)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line.graphic_obj)

        self.update_diagram_element(device=transformer, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_vsc(self, line: Line):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: Nothing
        """
        vsc = self.circuit.convert_line_to_vsc(line)

        # add device to the schematic
        graphic_obj = self.add_api_vsc(vsc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line.graphic_obj)

        self.update_diagram_element(device=vsc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_line_to_upfc(self, line: Line):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: Nothing
        """
        upfc = self.circuit.convert_line_to_upfc(line)

        # add device to the schematic
        graphic_obj = self.add_api_upfc(upfc)

        # update position
        graphic_obj.fromPort.update()
        graphic_obj.toPort.update()

        # delete from the schematic
        self.diagramScene.removeItem(line.graphic_obj)

        self.update_diagram_element(device=upfc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_obj)
        self.delete_diagram_element(device=line)

    def convert_generator_to_battery(self, gen: Generator):
        """
        Convert a generator to a battery
        :param gen: Generator instance
        :return: Nothing
        """
        battery = self.circuit.convert_generator_to_battery(gen)

        # add device to the schematic
        battery.graphic_obj = gen.bus.graphic_obj.add_battery(battery)

        # delete from the schematic
        gen.graphic_obj.remove(ask=False)

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

                bus.graphic_obj = self.add_api_bus(bus, explode_factor)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(lines)
        for i, branch in enumerate(lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(dc_lines)
        for i, branch in enumerate(dc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_dc_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer devices')

        nn = len(transformers2w)
        for i, branch in enumerate(transformers2w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_transformer(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer3w devices')

        nn = len(transformers3w)
        for i, elm in enumerate(transformers3w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            elm.graphic_obj = self.add_api_transformer_3w(elm, explode_factor)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic HVDC devices')

        nn = len(hvdc_lines)
        for i, branch in enumerate(hvdc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_hvdc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic VSC devices')

        nn = len(vsc_devices)
        for i, branch in enumerate(vsc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_vsc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic UPFC devices')

        nn = len(upfc_devices)
        for i, branch in enumerate(upfc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            branch.graphic_obj = self.add_api_upfc(branch)

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
        for elm in self.circuit.buses:
            if elm.graphic_obj is not None:
                elm.graphic_obj.recolour_mode()

        for elm in self.circuit.get_branches():
            if elm.graphic_obj is not None:
                elm.graphic_obj.recolour_mode()

        for elm in self.circuit.transformers3w:
            if elm.graphic_obj is not None:
                elm.graphic_obj.recolour_mode()

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
                       branches: List[Union[Line, DcLine, Transformer2W, Warning, UPFC, VSC]],
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

        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage', 'PVB']
        max_flow = 1

        for i, bus in enumerate(buses):

            location = self.diagram.query_point(bus)

            if location:

                if location.graphic_object:

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

                        location.graphic_object.set_tile_color(QColor(r, g, b, a))

                        tooltip = str(i) + ': ' + bus.name
                        if types is not None:
                            tooltip += ': ' + bus_types[types[i]]
                        tooltip += '\n'

                        tooltip += "%-10s %10.4f < %10.4fº [p.u.]\n" % ("V", vabs[i], vang[i])
                        tooltip += "%-10s %10.4f < %10.4fº [kV]\n" % ("V", vabs[i] * bus.Vnom, vang[i])

                        if Sbus is not None:
                            tooltip += "%-10s %10.4f [MW]\n" % ("P", Sbus[i].real)
                            tooltip += "%-10s %10.4f [MVAr]\n" % ("Q", Sbus[i].imag)

                        location.graphic_object.setToolTip(tooltip)

                        if use_flow_based_width:
                            h = int(np.floor(min_bus_width + Pnorm[i] * (max_bus_width - min_bus_width)))
                            location.graphic_object.change_size(location.graphic_object.w, h)

                    else:
                        location.graphic_object.set_tile_color(Qt.gray)

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

                            if br_active[i]:

                                if use_flow_based_width:
                                    w = int(
                                        np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                                else:
                                    w = location.graphic_object.pen_width

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

                                location.graphic_object.setToolTipText(tooltip)
                                location.graphic_object.set_colour(color, w, style)

                                if hasattr(location.graphic_object, 'set_arrows_with_power'):
                                    location.graphic_object.set_arrows_with_power(Sf=Sf[i] if Sf is not None else None,
                                                                                  St=St[i] if St is not None else None)
                            else:
                                w = location.graphic_object.pen_width
                                style = Qt.DashLine
                                color = Qt.gray
                                location.graphic_object.set_pen(QPen(color, w, style))
                        else:
                            print("Branch {0} {1} has no graphic object!!".format(branch.name, branch.idtag))

        if hvdc_Pf is not None:

            hvdc_sending_power_norm = np.abs(hvdc_Pf) / (max_flow + 1e-20)

            for i, elm in enumerate(hvdc_lines):

                location = self.diagram.query_point(branches[i])

                if location:

                    if location.graphic_object:

                        if hvdc_active[i]:

                            if use_flow_based_width:
                                w = int(np.floor(
                                    min_branch_width + hvdc_sending_power_norm[i] * (
                                                max_branch_width - min_branch_width)))
                            else:
                                w = location.graphic_object.pen_width

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

                            location.graphic_object.setToolTipText(tooltip)
                            location.graphic_object.set_colour(color, w, style)

                        else:
                            w = location.graphic_object.pen_width
                            style = Qt.DashLine
                            color = Qt.gray
                            location.graphic_object.set_pen(QPen(color, w, style))
                    else:
                        print("HVDC line {0} {1} has no graphic object!!".format(elm.name, elm.idtag))

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
                            # if the bus was not added in the first pass and is in the original diagram, add it now
                            diagram.set_point(device=bus,
                                              location=location)
                            bus_dict[bus.idtag] = location.graphic_object

        return diagram


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

    window = GridEditorWidget(circuit=MultiCircuit(),
                              diagram=BusBranchDiagram())

    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
