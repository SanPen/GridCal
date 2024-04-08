# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import os
from typing import List, Tuple, Union

import networkx as nx
import numpy as np
from PySide6 import QtGui, QtWidgets, QtCore
from matplotlib import pyplot as plt
from pandas.plotting import register_matplotlib_converters

import GridCalEngine.Devices as dev
import GridCalEngine.Simulations as sim
import GridCal.Gui.GuiFunctions as gf
import GridCal.Gui.Visualization.palettes as palettes
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCal.Gui.GeneralDialogues import CheckListDialogue, StartEndSelectionDialogue, InputSearchDialogue, \
    InputNumberDialogue
from GridCalEngine.Devices.types import ALL_DEV_TYPES

from GridCal.Gui.Diagrams.DiagramEditorWidget.diagram_editor_widget import (DiagramEditorWidget,
                                                                            BusGraphicItem,
                                                                            generate_bus_branch_diagram,
                                                                            make_vecinity_diagram)
from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, generate_map_diagram
from GridCal.Gui.Diagrams.diagrams_model import DiagramsModel
from GridCal.Gui.messages import yes_no_question, error_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.compiled_arrays import CompiledArraysMain
from GridCal.Gui.Main.object_select_window import ObjectSelectWindow
from GridCal.Gui.Diagrams.MapWidget.TileProviders.blue_marble import BlueMarbleTiles
from GridCal.Gui.Diagrams.MapWidget.TileProviders.cartodb import CartoDbTiles

ALL_EDITORS = Union[DiagramEditorWidget, GridMapWidget]
ALL_EDITORS_NONE = Union[None, DiagramEditorWidget, GridMapWidget]


class DiagramsMain(CompiledArraysMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        CompiledArraysMain.__init__(self, parent)

        # list of diagrams
        self.diagram_widgets_list: List[ALL_EDITORS] = list()

        # Declare the map
        palettes_list = [palettes.Colormaps.GridCal,
                         palettes.Colormaps.Green2Red,
                         palettes.Colormaps.Heatmap,
                         palettes.Colormaps.TSO]
        self.cmap_dict = {e.value: e for e in palettes_list}
        self.ui.palette_comboBox.setModel(gf.get_list_model([e.value for e in palettes_list]))

        # map tile sources
        self.tile_sources = {
            'Blue Marble': BlueMarbleTiles(tiles_dir=os.path.join(get_create_gridcal_folder(), 'tiles', 'blue_marble')),
            'Carto positron': CartoDbTiles(
                tiles_dir=os.path.join(get_create_gridcal_folder(), 'tiles', 'carto_db_positron'),
                tile_servers=['http://basemaps.cartocdn.com/light_all/']),
            'Carto dark matter': CartoDbTiles(
                tiles_dir=os.path.join(get_create_gridcal_folder(), 'tiles', 'carto_db_dark_matter'),
                tile_servers=["http://basemaps.cartocdn.com/dark_all/"])
        }

        self.ui.tile_provider_comboBox.setModel(gf.get_list_model(list(self.tile_sources.keys())))
        self.ui.tile_provider_comboBox.setCurrentIndex(0)

        # Automatic layout modes
        self.layout_algorithms_dict = dict()
        self.layout_algorithms_dict['circular_layout'] = nx.circular_layout
        self.layout_algorithms_dict['random_layout'] = nx.random_layout
        self.layout_algorithms_dict['shell_layout'] = nx.shell_layout
        self.layout_algorithms_dict['spring_layout'] = nx.spring_layout
        self.layout_algorithms_dict['spectral_layout'] = nx.spectral_layout
        self.layout_algorithms_dict['fruchterman_reingold_layout'] = nx.fruchterman_reingold_layout
        self.layout_algorithms_dict['kamada_kawai'] = nx.kamada_kawai_layout

        mdl = gf.get_list_model(list(self.layout_algorithms_dict.keys()))
        self.ui.automatic_layout_comboBox.setModel(mdl)
        self.ui.automatic_layout_comboBox.setCurrentIndex(6)

        # list of steps in the schematic
        self.schematic_list_steps = list()

        self.available_results_steps_dict = None

        # list of styles
        plt_styles = plt.style.available
        self.ui.plt_style_comboBox.setModel(gf.get_list_model(plt_styles))

        if 'fivethirtyeight' in plt_styles:
            self.ui.plt_style_comboBox.setCurrentText('fivethirtyeight')

        # configure matplotlib for pandas time series
        register_matplotlib_converters()

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionExport.triggered.connect(self.export_diagram)
        self.ui.actionDelete_selected.triggered.connect(self.delete_selected_from_the_schematic)
        self.ui.actionTry_to_fix_buses_location.triggered.connect(self.try_to_fix_buses_location)
        self.ui.actionSet_schematic_positions_from_GPS_coordinates.triggered.connect(self.set_xy_from_lat_lon)
        self.ui.actionSetSelectedBusCountry.triggered.connect(lambda: self.set_selected_bus_property('country'))
        self.ui.actionSetSelectedBusArea.triggered.connect(lambda: self.set_selected_bus_property('area'))
        self.ui.actionSetSelectedBusZone.triggered.connect(lambda: self.set_selected_bus_property('zone'))
        self.ui.actionSelect_buses_by_area.triggered.connect(lambda: self.select_buses_by_property('area'))
        self.ui.actionSelect_buses_by_zone.triggered.connect(lambda: self.select_buses_by_property('zone'))
        self.ui.actionSelect_buses_by_country.triggered.connect(lambda: self.select_buses_by_property('country'))
        self.ui.actionAdd_selected_to_contingency.triggered.connect(self.add_selected_to_contingency)
        self.ui.actionAdd_selected_as_new_investment.triggered.connect(self.add_selected_to_investment)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out)
        self.ui.actionAdd_general_bus_branch_diagram.triggered.connect(self.add_complete_bus_branch_diagram)
        self.ui.actionNew_bus_branch_diagram_from_selection.triggered.connect(
            self.new_bus_branch_diagram_from_selection)
        self.ui.actionAdd_map.triggered.connect(self.add_map_diagram)
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)
        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)
        self.ui.actionCenter_view.triggered.connect(self.center_nodes)
        self.ui.actionAutoatic_layout.triggered.connect(self.auto_layout)
        self.ui.actionSearchDiagram.triggered.connect(self.search_diagram)
        self.ui.actionEdit_simulation_time_limits.triggered.connect(self.edit_time_interval)
        self.ui.actionDisable_all_results_tags.triggered.connect(self.disable_all_results_tags)
        self.ui.actionEnable_all_results_tags.triggered.connect(self.enable_all_results_tags)

        # Buttons
        self.ui.colour_results_pushButton.clicked.connect(self.colour_diagrams)

        # list clicks
        self.ui.diagramsListView.clicked.connect(self.set_selected_diagram_on_click)

        # combobox change
        self.ui.plt_style_comboBox.currentTextChanged.connect(self.plot_style_change)

        # sliders
        # self.ui.diagram_step_slider.sliderReleased.connect(self.diagrams_time_slider_change)
        self.ui.diagram_step_slider.valueChanged.connect(self.diagrams_time_slider_change)
        # self.ui.db_step_slider.sliderReleased.connect(self.objects_time_slider_change)
        self.ui.db_step_slider.valueChanged.connect(self.objects_time_slider_change)

        # spinbox change
        self.ui.explosion_factor_doubleSpinBox.valueChanged.connect(self.explosion_factor_change)
        self.ui.defaultBusVoltageSpinBox.valueChanged.connect(self.default_voltage_change)

        # context menu
        self.ui.diagramsListView.customContextMenuRequested.connect(self.show_diagrams_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.diagramsListView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:
            if isinstance(diagram_widget, DiagramEditorWidget):

                # guilty assumption
                do_it = True

                # if the ask, checkbox is checked, then ask
                if self.ui.ask_before_appliying_layout_checkBox.isChecked():
                    reply = QtWidgets.QMessageBox.question(self, 'Message',
                                                           'Are you sure that you want to try an automatic layout?',
                                                           QtWidgets.QMessageBox.StandardButton.Yes,
                                                           QtWidgets.QMessageBox.StandardButton.No)

                    if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                        do_it = True
                    else:
                        do_it = False

                if do_it:
                    diagram_widget.auto_layout(sel=self.ui.automatic_layout_comboBox.currentText())

            else:
                info_msg("The current diagram cannot be automatically layed out")
        else:
            pass  # asked and decided ot to change the layout

    def bigger_nodes(self):
        """
        Move the nodes more separated
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.expand_node_distances()
                diagram.center_nodes()

    def smaller_nodes(self):
        """
        Move the nodes closer
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.shrink_node_distances()
                diagram.center_nodes()

    def center_nodes(self):
        """
        Center the nodes in the screen
        """

        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):
                selected = self.get_selected_buses()

                if len(selected) == 0:
                    buses = self.circuit.buses
                else:
                    buses = [b for i, b, graphic in selected]

                diagram.center_nodes(elements=buses)

    def get_selected_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, DiagramEditorWidget):
            return diagram_widget.get_selected_buses()
        else:
            return list()

    def get_current_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, DiagramEditorWidget):
            return diagram_widget.get_buses()
        else:
            return list()

    def explosion_factor_change(self):
        """
        Change the node explosion factor
        """
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.expand_factor = self.ui.explosion_factor_doubleSpinBox.value()

    def zoom_in(self):
        """
        Zoom the diagram in
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.editor_graphics_view.zoom_in()
            elif isinstance(diagram, GridMapWidget):
                # TODO implement this
                pass

    def zoom_out(self):
        """
        Zoom the diagram out
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.editor_graphics_view.zoom_out()
            elif isinstance(diagram, GridMapWidget):
                # TODO implement this
                pass

    def edit_time_interval(self):
        """
        Run the simulation limits adjust window
        """

        if self.circuit.has_time_series:
            self.start_end_dialogue_window = StartEndSelectionDialogue(min_value=self.simulation_start_index,
                                                                       max_value=self.simulation_end_index,
                                                                       time_array=self.circuit.time_profile)

            self.start_end_dialogue_window.setModal(True)
            self.start_end_dialogue_window.exec()

            if self.start_end_dialogue_window.is_accepted:
                self.setup_sim_indices(st=self.start_end_dialogue_window.start_value,
                                       en=self.start_end_dialogue_window.end_value)
        else:
            info_msg("There are no time series :/")

    def grid_colour_function(self, plot_function, current_study: str, t_idx: Union[None, int]) -> None:
        """
        Colour the schematic or the map
        :param plot_function: function pointer to the function doing the plotting
        :param current_study: current_study name
        :param t_idx: current time step (if None, the snapshot is taken)
        """
        use_flow_based_width = self.ui.branch_width_based_on_flow_checkBox.isChecked()
        min_branch_width = self.ui.min_branch_size_spinBox.value()
        max_branch_width = self.ui.max_branch_size_spinBox.value()
        min_bus_width = self.ui.min_node_size_spinBox.value()
        max_bus_width = self.ui.max_node_size_spinBox.value()
        cmap_text = self.ui.palette_comboBox.currentText()

        cmap = self.cmap_dict[cmap_text]

        buses = self.circuit.buses
        branches = self.circuit.get_branches_wo_hvdc()
        hvdc_lines = self.circuit.hvdc_lines

        if current_study == sim.PowerFlowDriver.tpe.value:
            if t_idx is None:
                results: sim.PowerFlowResults = self.session.get_results(sim.SimulationTypes.PowerFlow_run)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.Sbus,
                                     bus_active=bus_active,
                                     Sf=results.Sf,
                                     St=results.St,
                                     voltages=results.voltage,
                                     loadings=np.abs(results.loading),
                                     types=results.bus_types,
                                     losses=results.losses,
                                     br_active=br_active,
                                     hvdc_Pf=results.hvdc_Pf,
                                     hvdc_Pt=results.hvdc_Pt,
                                     hvdc_losses=results.hvdc_losses,
                                     hvdc_loading=results.hvdc_loading,
                                     hvdc_active=hvdc_active,
                                     ma=results.tap_module,
                                     theta=results.tap_angle,
                                     Beq=results.Beq,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.PowerFlowTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                results: sim.PowerFlowTimeSeriesResults = self.session.get_results(sim.SimulationTypes.TimeSeries_run)
                bus_active = [bus.active_prof[t_idx] for bus in self.circuit.buses]
                br_active = [br.active_prof[t_idx] for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active_prof[t_idx] for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.S[t_idx, :],
                                     bus_active=bus_active,
                                     Sf=results.Sf[t_idx, :],
                                     St=results.St[t_idx, :],
                                     voltages=results.voltage[t_idx, :],
                                     loadings=np.abs(results.loading[t_idx, :]),
                                     types=results.bus_types,
                                     losses=results.losses[t_idx, :],
                                     br_active=br_active,
                                     hvdc_Pf=results.hvdc_Pf[t_idx, :],
                                     hvdc_Pt=results.hvdc_Pt[t_idx, :],
                                     hvdc_losses=results.hvdc_losses[t_idx, :],
                                     hvdc_loading=results.hvdc_loading[t_idx, :],
                                     hvdc_active=hvdc_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.ContinuationPowerFlowDriver.tpe.value:
            if t_idx is None:
                results: sim.ContinuationPowerFlowResults = self.session.get_results(
                    sim.SimulationTypes.ContinuationPowerFlow_run
                )
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.Sbus[t_idx, :],
                                     bus_active=bus_active,
                                     Sf=results.Sf[t_idx, :],
                                     St=results.St[t_idx, :],
                                     voltages=results.voltages[t_idx, :],
                                     types=results.bus_types,
                                     loadings=np.abs(results.loading[t_idx, :]),
                                     br_active=br_active,
                                     hvdc_Pf=None,
                                     hvdc_Pt=None,
                                     hvdc_losses=None,
                                     hvdc_loading=None,
                                     hvdc_active=None,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.StochasticPowerFlowDriver.tpe.value:
            if t_idx is None:
                results: sim.StochasticPowerFlowResults = self.session.get_results(
                    sim.SimulationTypes.StochasticPowerFlow)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
                # hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.S_points.mean(axis=0),
                                     types=results.bus_types,
                                     voltages=results.V_points.mean(axis=0),
                                     bus_active=bus_active,
                                     loadings=np.abs(results.loading_points).mean(axis=0),
                                     Sf=results.Sbr_points.mean(axis=0),
                                     St=-results.Sbr_points.mean(axis=0),
                                     br_active=br_active,
                                     hvdc_Pf=None,
                                     hvdc_Pt=None,
                                     hvdc_losses=None,
                                     hvdc_loading=None,
                                     hvdc_active=None,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.ShortCircuitDriver.tpe.value:
            if t_idx is None:
                results: sim.ShortCircuitResults = self.session.get_results(sim.SimulationTypes.ShortCircuit_run)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.Sbus1,
                                     bus_active=bus_active,
                                     Sf=results.Sf1,
                                     St=results.St1,
                                     voltages=results.voltage1,
                                     types=results.bus_types,
                                     loadings=results.loading1,
                                     br_active=br_active,
                                     hvdc_Pf=None,
                                     hvdc_Pt=None,
                                     hvdc_losses=None,
                                     hvdc_loading=None,
                                     hvdc_active=None,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.OptimalPowerFlowDriver.tpe.value:
            if t_idx is None:
                results: sim.OptimalPowerFlowResults = self.session.get_results(sim.SimulationTypes.OPF_run)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.Sbus,
                                     voltages=results.voltage,
                                     bus_active=bus_active,
                                     loadings=results.loading,
                                     types=results.bus_types,
                                     Sf=results.Sf,
                                     St=results.St,
                                     br_active=br_active,
                                     hvdc_Pf=results.hvdc_Pf,
                                     hvdc_Pt=-results.hvdc_Pf,
                                     hvdc_loading=results.hvdc_loading,
                                     hvdc_active=hvdc_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.OptimalPowerFlowTimeSeriesDriver.tpe.value:

            if t_idx is not None:
                results: sim.OptimalPowerFlowTimeSeriesResults = self.session.get_results(
                    sim.SimulationTypes.OPFTimeSeries_run
                )
                bus_active = [bus.active_prof[t_idx] for bus in self.circuit.buses]
                br_active = [br.active_prof[t_idx] for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active_prof[t_idx] for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     voltages=results.voltage[t_idx, :],
                                     Sbus=results.Sbus[t_idx, :],
                                     types=results.bus_types,
                                     bus_active=bus_active,
                                     Sf=results.Sf[t_idx, :],
                                     St=results.St[t_idx, :],
                                     loadings=np.abs(results.loading[t_idx, :]),
                                     br_active=br_active,
                                     hvdc_Pf=results.hvdc_Pf[t_idx, :],
                                     hvdc_Pt=-results.hvdc_Pf[t_idx, :],
                                     hvdc_loading=results.hvdc_loading[t_idx, :],
                                     hvdc_active=hvdc_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.LinearAnalysisDriver.tpe.value:
            if t_idx is None:
                results: sim.LinearAnalysisResults = self.session.get_results(sim.SimulationTypes.LinearAnalysis_run)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]
                voltage = np.ones(self.circuit.get_bus_number())

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     voltages=voltage,
                                     Sbus=results.Sbus,
                                     types=results.bus_types,
                                     bus_active=bus_active,
                                     Sf=results.Sf,
                                     St=-results.Sf,
                                     loadings=results.loading,
                                     br_active=br_active,
                                     loading_label='Loading',
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.LinearAnalysisTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                results: sim.LinearAnalysisTimeSeriesResults = self.session.get_results(
                    sim.SimulationTypes.LinearAnalysis_TS_run)
                bus_active = [bus.active_prof[t_idx] for bus in self.circuit.buses]
                br_active = [br.active_prof[t_idx] for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active_prof[t_idx] for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.S[t_idx],
                                     voltages=results.voltage[t_idx],
                                     types=results.bus_types,
                                     bus_active=bus_active,
                                     Sf=results.Sf[t_idx],
                                     St=-results.Sf[t_idx],
                                     loadings=np.abs(results.loading[t_idx]),
                                     br_active=br_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.ContingencyAnalysisDriver.tpe.value:

            if t_idx is None:
                results: sim.ContingencyAnalysisResults = self.session.get_results(
                    sim.SimulationTypes.ContingencyAnalysis_run)
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]
                con_idx = 0
                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=results.Sbus[con_idx, :],
                                     voltages=results.voltage[con_idx, :],
                                     types=results.bus_types,
                                     bus_active=bus_active,
                                     Sf=results.Sf[con_idx, :],
                                     St=-results.Sf[con_idx, :],
                                     loadings=np.abs(results.loading[con_idx, :]),
                                     br_active=br_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.ContingencyAnalysisTimeSeries.tpe.value:
            if t_idx is not None:
                results: sim.ContingencyAnalysisTimeSeriesResults = self.session.get_results(
                    sim.SimulationTypes.ContingencyAnalysisTS_run)
                bus_active = [bus.active_prof[t_idx] for bus in self.circuit.buses]
                br_active = [br.active_prof[t_idx] for br in self.circuit.get_branches_wo_hvdc()]
                hvdc_active = [hvdc.active_prof[t_idx] for hvdc in self.circuit.hvdc_lines]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     voltages=np.ones(results.nbus, dtype=complex),
                                     Sbus=results.S[t_idx, :],
                                     types=results.bus_types,
                                     bus_active=bus_active,
                                     Sf=results.max_flows[t_idx, :],
                                     St=-results.max_flows[t_idx, :],
                                     loadings=np.abs(results.max_loading[t_idx]),
                                     br_active=br_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.InputsAnalysisDriver.tpe.value:

            if t_idx is None:
                results = self.session.get_results(sim.SimulationTypes.InputsAnalysis_run)
                nbus = self.circuit.get_bus_number()
                nbr = self.circuit.get_branch_number()
                bus_active = [bus.active for bus in self.circuit.buses]
                br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]

                return plot_function(buses=buses,
                                     branches=branches,
                                     hvdc_lines=hvdc_lines,
                                     Sbus=np.zeros(nbus, dtype=complex),
                                     voltages=np.ones(nbus, dtype=complex),
                                     bus_active=bus_active,
                                     Sf=np.zeros(nbr, dtype=complex),
                                     St=np.zeros(nbr, dtype=complex),
                                     loadings=np.zeros(nbr, dtype=complex),
                                     br_active=br_active,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width,
                                     cmap=cmap)
            else:
                info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.AvailableTransferCapacityTimeSeriesDriver.tpe.value:
            pass

        elif current_study == sim.AvailableTransferCapacityDriver.tpe.value:
            pass

        elif current_study == 'Transient stability':
            raise Exception('Not implemented :(')

        else:
            print('grid_colour_function: <' + current_study + '> Not implemented :(')

    def colour_diagrams(self) -> None:
        """
        Color the grid now
        """

        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:

            current_study = self.ui.available_results_to_color_comboBox.currentText()
            val = self.ui.diagram_step_slider.value()
            t_idx = val if val > -1 else None

            for diagram in self.diagram_widgets_list:

                if isinstance(diagram, DiagramEditorWidget):
                    self.grid_colour_function(plot_function=diagram.colour_results,
                                              current_study=current_study,
                                              t_idx=t_idx)

                elif isinstance(diagram, GridMapWidget):
                    self.grid_colour_function(plot_function=diagram.colour_results,
                                              current_study=current_study,
                                              t_idx=t_idx)

    def set_diagrams_list_view(self) -> None:
        """
        Create the diagrams list view
        """
        mdl = DiagramsModel(self.diagram_widgets_list)
        self.ui.diagramsListView.setModel(mdl)

    def get_selected_diagram_widget(self) -> ALL_EDITORS_NONE:
        """
        Get the currently selected diagram
        :return: None, DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        indices = self.ui.diagramsListView.selectedIndexes()

        if len(indices):
            idx = indices[0].row()
            return self.diagram_widgets_list[idx]
        else:
            return None

    def redraw_current_diagram(self):
        """
        Redraw the currently selected diagram
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:

            if isinstance(diagram_widget, DiagramEditorWidget):
                # set pointer to the circuit
                diagram = generate_bus_branch_diagram(buses=self.circuit.buses,
                                                      lines=self.circuit.lines,
                                                      dc_lines=self.circuit.dc_lines,
                                                      transformers2w=self.circuit.transformers2w,
                                                      transformers3w=self.circuit.transformers3w,
                                                      windings=self.circuit.windings,
                                                      hvdc_lines=self.circuit.hvdc_lines,
                                                      vsc_devices=self.circuit.vsc_devices,
                                                      upfc_devices=self.circuit.upfc_devices,
                                                      fluid_nodes=self.circuit.fluid_nodes,
                                                      fluid_paths=self.circuit.fluid_paths,
                                                      explode_factor=1.0,
                                                      prog_func=None,
                                                      text_func=None)

                diagram_widget.set_data(circuit=self.circuit,
                                        diagram=diagram)

    def set_selected_diagram_on_click(self):
        """
        on list-view click, set the currentlt selected diagram widget
        """
        diagram = self.get_selected_diagram_widget()

        if diagram:
            self.set_diagram_widget(diagram)

    def add_complete_bus_branch_diagram_now(self, name='All bus branches') -> DiagramEditorWidget:
        """
        Add ageneral bus-branch diagram
        :return DiagramEditorWidget
        """
        diagram = generate_bus_branch_diagram(buses=self.circuit.get_buses(),
                                              lines=self.circuit.get_lines(),
                                              dc_lines=self.circuit.get_dc_lines(),
                                              transformers2w=self.circuit.get_transformers2w(),
                                              transformers3w=self.circuit.get_transformers3w(),
                                              windings=self.circuit.get_windings(),
                                              hvdc_lines=self.circuit.get_hvdc(),
                                              vsc_devices=self.circuit.get_vsc(),
                                              upfc_devices=self.circuit.get_upfc(),
                                              fluid_nodes=self.circuit.get_fluid_nodes(),
                                              fluid_paths=self.circuit.get_fluid_paths(),
                                              explode_factor=1.0,
                                              prog_func=None,
                                              text_func=None,
                                              name=name)

        diagram_widget = DiagramEditorWidget(circuit=self.circuit,
                                             diagram=diagram,
                                             default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                             time_index=self.get_diagram_slider_index())

        diagram_widget.setStretchFactor(1, 10)
        diagram_widget.center_nodes()
        self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram_widget)

        return diagram_widget

    def add_complete_bus_branch_diagram(self) -> None:
        """
        Add ageneral bus-branch diagram
        """
        self.add_complete_bus_branch_diagram_now(name='All bus branches')

    def new_bus_branch_diagram_from_selection(self):
        """
        Add a bus-branch diagram of a particular selection of objects
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:

            if isinstance(diagram_widget, DiagramEditorWidget):
                diagram = diagram_widget.get_selection_diagram()

                diagram_widget = DiagramEditorWidget(self.circuit,
                                                     diagram=diagram,
                                                     default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                     time_index=self.get_diagram_slider_index())

                self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
                self.set_diagrams_list_view()

    def add_bus_vecinity_diagram_from_model(self):
        """
        Add a bus vecinity diagram
        :return:
        """
        model = self.ui.dataStructureTableView.model()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = {idx.row() for idx in sel_idx}
                    sel_obj = [objects[idx] for idx in unique][0]
                    root_bus = None
                    if isinstance(sel_obj, dev.Bus):
                        root_bus = sel_obj

                    elif isinstance(sel_obj, dev.Generator):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Battery):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Load):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Shunt):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Line):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.Transformer2W):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.DcLine):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.HvdcLine):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.VSC):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.UPFC):
                        root_bus = sel_obj.bus_from

                    if root_bus is not None:

                        dlg = InputNumberDialogue(min_value=1, max_value=99,
                                                  default_value=1, is_int=True,
                                                  title='Vecinity diagram',
                                                  text='Select the expansion level')

                        if dlg.exec():
                            diagram = make_vecinity_diagram(circuit=self.circuit,
                                                            root_bus=root_bus,
                                                            max_level=dlg.value)

                            diagram_widget = DiagramEditorWidget(self.circuit,
                                                                 diagram=diagram,
                                                                 default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                                 time_index=self.get_diagram_slider_index())

                            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                                diagram=diagram)
                            self.set_diagrams_list_view()

    def create_circuit_stored_diagrams(self):
        """
        Create as Widgets the diagrams stored in the circuit
        :return:
        """
        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()

        for diagram in self.circuit.diagrams:

            if isinstance(diagram, dev.BusBranchDiagram):
                diagram_widget = DiagramEditorWidget(self.circuit,
                                                     diagram=diagram,
                                                     default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                     time_index=self.get_diagram_slider_index())
                diagram_widget.setStretchFactor(1, 10)
                diagram_widget.center_nodes()
                self.diagram_widgets_list.append(diagram_widget)

            elif isinstance(diagram, dev.MapDiagram):
                # select the tile source
                tile_source = self.tile_sources[self.ui.tile_provider_comboBox.currentText()]

                # create the map widget
                map_widget = GridMapWidget(parent=None,
                                           tile_src=tile_source,
                                           start_level=diagram.start_level,
                                           longitude=diagram.longitude,
                                           latitude=diagram.latitude,
                                           name=diagram.name,
                                           diagram=diagram)

                # map_widget.GotoLevelAndPosition(5, -15.41, 40.11)
                self.diagram_widgets_list.append(map_widget)

            else:
                raise Exception("Unknown diagram type")

        self.set_diagrams_list_view()

    def add_map_diagram(self) -> None:
        """
        Adds a Map diagram
        """
        # select the tile source
        tile_source = self.tile_sources[self.ui.tile_provider_comboBox.currentText()]

        diagram = generate_map_diagram(substations=self.circuit.get_substations(),
                                       voltage_levels=self.circuit.get_voltage_levels(),
                                       lines=self.circuit.get_lines(),
                                       dc_lines=self.circuit.get_dc_lines(),
                                       hvdc_lines=self.circuit.get_hvdc(),
                                       fluid_nodes=self.circuit.get_fluid_nodes(),
                                       fluid_paths=self.circuit.get_fluid_paths(),
                                       prog_func=None,
                                       text_func=None,
                                       name='Map diagram')

        # create the map widget
        map_widget = GridMapWidget(parent=None,
                                   tile_src=tile_source,
                                   start_level=5,
                                   longitude=-15.41,
                                   latitude=40.11,
                                   name='Map diagram',
                                   diagram=diagram)

        self.add_diagram_widget_and_diagram(diagram_widget=map_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(widget=map_widget)

    def add_diagram_widget_and_diagram(self,
                                       diagram_widget: ALL_EDITORS,
                                       diagram: Union[dev.BusBranchDiagram, dev.MapDiagram]):
        """
        Add diagram widget, it also adds the diagram to the circuit for later
        :param diagram_widget: Diagram widget object
        :param diagram: BusBranchDiagram or MapDiagram
        """

        # add the widget pointer
        self.diagram_widgets_list.append(diagram_widget)

        # add the diagram to the circuit
        self.circuit.add_diagram(diagram)

    def remove_diagram(self):
        """
        Remove diagram
        """
        diagram_widget = self.get_selected_diagram_widget()
        if diagram_widget is not None:
            ok = yes_no_question("Are you sure that you want to remove " + diagram_widget.name + "?",
                                 "Remove diagram")

            if ok:
                # remove the widget
                self.diagram_widgets_list.remove(diagram_widget)

                # remove the diagram
                self.circuit.remove_diagram(diagram_widget.diagram)

                # remove it from the layout list
                self.remove_all_diagram_widgets()

                # update view
                self.set_diagrams_list_view()

    def remove_all_diagrams(self) -> None:
        """
        Remove all diagrams and their widgets
        """
        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()
        self.ui.diagramsListView.setModel(None)

    def remove_all_diagram_widgets(self) -> None:
        """
        Remove all diagram widgets from the container
        """
        # remove all widgets from the layout
        for i in reversed(range(self.ui.schematic_layout.count())):
            # get the widget
            widget_to_remove = self.ui.schematic_layout.itemAt(i).widget()

            # remove it from the layout list
            self.ui.schematic_layout.removeWidget(widget_to_remove)

            # remove it from the gui
            widget_to_remove.setParent(None)

    def set_diagram_widget(self, widget: ALL_EDITORS):
        """
        Set the current diagram in the container
        :param widget: DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        self.remove_all_diagram_widgets()

        # add the new diagram
        self.ui.schematic_layout.addWidget(widget)

        # set the alignment
        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 2)

        # set the selected index
        row = self.diagram_widgets_list.index(widget)
        index = self.ui.diagramsListView.model().index(row, 0)
        self.ui.diagramsListView.setCurrentIndex(index)

    def plot_style_change(self):
        """
        Change the style
        """
        style = self.ui.plt_style_comboBox.currentText()
        plt.style.use(style)

    def diagrams_time_slider_change(self) -> None:
        """
        After releasing the time slider, do something
        """
        self.update_diagram_time_slider_texts()
        idx = self.ui.diagram_step_slider.value()

        # correct to interpret -1 as None
        idx2 = idx if idx > -1 else None

        # modify the time index in all the bus-branch diagrams
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.set_time_index(time_index=idx2)

                # TODO: consider other diagrams

    def update_diagram_time_slider_texts(self):
        """
        Update the slider text label as it is moved
        :return:
        """
        idx = self.ui.diagram_step_slider.value()

        if idx > -1:
            val = f"[{idx}] {self.circuit.time_profile[idx]}"
            self.ui.schematic_step_label.setText(val)
        else:
            self.ui.schematic_step_label.setText("Snapshot")

    def objects_time_slider_change(self) -> None:
        """
        After releasing the time slider, do something
        """
        self.objects_diagram_time_slider_texts()

        idx = self.ui.db_step_slider.value()

        # correct to interpret -1 as None
        idx2 = idx if idx > -1 else None

        # modify the time index in the current DB objects model
        mdl = self.ui.dataStructureTableView.model()
        if isinstance(mdl, gf.ObjectsModel):
            mdl.set_time_index(time_index=idx2)

    def objects_diagram_time_slider_texts(self):
        """
        Update the slider text label as it is moved
        :return:
        """
        idx = self.ui.db_step_slider.value()

        if idx > -1:
            val = f"[{idx}] {self.circuit.time_profile[idx]}"
            self.ui.db_step_label.setText(val)
        else:
            self.ui.db_step_label.setText("Snapshot")

    def export_diagram(self):
        """
        Save the schematic
        :return:
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, DiagramEditorWidget):

                # declare the allowed file types
                files_types = "Scalable Vector Graphics (*.svg);;Portable Network Graphics (*.png)"

                fname = str(os.path.join(self.project_directory, self.ui.grid_name_line_edit.text()))

                # call dialog to select the file
                filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

                if not (filename.endswith('.svg') or filename.endswith('.png')):
                    filename += ".svg"

                if filename != "":
                    # save in factor * K
                    factor = self.ui.resolution_factor_spinBox.value()
                    w = 1920 * factor
                    h = 1080 * factor
                    diagram.export(filename, w, h)

    def set_xy_from_lat_lon(self):
        """
        Get the x, y coordinates of the buses from their latitude and longitude
        """
        if len(self.circuit.buses) > 0:

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, DiagramEditorWidget):

                    if yes_no_question("All nodes in the current diagram will be positioned to a 2D plane projection "
                                       "of their latitude and longitude. "
                                       "Are you sure of this?"):
                        diagram.fill_xy_from_lat_lon(destructive=True)
                        diagram.center_nodes()

    def set_big_bus_marker(self, buses: List[dev.Bus], color: QtGui.QColor):
        """
        Set a big marker at the selected buses
        :param buses: list of Bus objects
        :param color: colour to use
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, DiagramEditorWidget):
                diagram.set_big_bus_marker(buses=buses, color=color)

    def set_big_bus_marker_colours(self,
                                   buses: List[dev.Bus],
                                   colors: List[type(QtGui.QColor)],
                                   tool_tips: Union[None, List[str]] = None):
        """
        Set a big marker at the selected buses with the matching colours
        :param buses: list of Bus objects
        :param colors: list of colour to use
        :param tool_tips: list of tool tips (optional)
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, DiagramEditorWidget):
                diagram.set_big_bus_marker_colours(buses=buses,
                                                   colors=colors,
                                                   tool_tips=tool_tips)

    def clear_big_bus_markers(self):
        """
        Set a big marker at the selected buses
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, DiagramEditorWidget):
                diagram.clear_big_bus_markers()

    def delete_selected_from_the_schematic(self):
        """
        Prompt to delete the selected buses from the schematic
        """

        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, DiagramEditorWidget):
            diagram_widget.delete_Selected()
        else:
            pass

    def try_to_fix_buses_location(self):
        """
        Try to fix the location of the buses
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, DiagramEditorWidget):
            selected_buses = diagram_widget.get_selected_buses()
            if len(selected_buses) > 0:
                diagram_widget.try_to_fix_buses_location(buses_selection=selected_buses)
            else:
                info_msg('Choose some elements from the schematic', 'Fix buses locations')

    def get_selected_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get the selected investment devices
        :return: list of selected devices
        """

        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, DiagramEditorWidget):
            lst = diagram.get_selection_api_objects()
        elif isinstance(diagram, GridMapWidget):
            lst = list()
        else:
            lst = list()

        return lst

    def add_selected_to_contingency(self):
        """
        Add contingencies from the schematic selection
        """
        if len(self.circuit.buses) > 0:

            # get the selected buses
            selected = self.get_selected_devices()

            if len(selected) > 0:
                names = [elm.type_name + ": " + elm.name for elm in selected]
                self.contingency_checks_diag = CheckListDialogue(objects_list=names, title="Add contingency")
                self.contingency_checks_diag.setModal(True)
                self.contingency_checks_diag.exec_()

                if self.contingency_checks_diag.is_accepted:

                    group = dev.ContingencyGroup(idtag=None,
                                                 name="Contingency " + str(len(self.circuit.contingency_groups)),
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_contingency_group(group)

                    for i in self.contingency_checks_diag.selected_indices:
                        elm = selected[i]
                        con = dev.Contingency(device_idtag=elm.idtag,
                                              code=elm.code,
                                              name=elm.name,
                                              prop="active",
                                              value=0,
                                              group=group)
                        self.circuit.add_contingency(con)
            else:
                info_msg("Select some elements in the schematic first", "Add selected to contingency")

    def add_selected_to_investment(self) -> None:
        """
        Add contingencies from the schematic selection
        """
        if len(self.circuit.buses) > 0:

            # get the selected investment devices
            selected = self.get_selected_devices()

            if len(selected) > 0:

                # launch selection dialogue to add/remove from the selection
                names = [elm.type_name + ": " + elm.name for elm in selected]
                self.investment_checks_diag = CheckListDialogue(objects_list=names, title="Add investment")
                self.investment_checks_diag.setModal(True)
                self.investment_checks_diag.exec_()

                if self.investment_checks_diag.is_accepted:

                    # create a new investments group
                    group = dev.InvestmentsGroup(idtag=None,
                                                 name="Investment " + str(len(self.circuit.contingency_groups)),
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_investments_group(group)

                    # add the selection as investments to the group
                    for i in self.investment_checks_diag.selected_indices:
                        elm = selected[i]
                        con = dev.Investment(device_idtag=elm.idtag,
                                             code=elm.code,
                                             name=elm.type_name + ": " + elm.name,
                                             CAPEX=0.0,
                                             OPEX=0.0,
                                             group=group)
                        self.circuit.add_investment(con)
            else:
                info_msg("Select some elements in the schematic first", "Add selected to investment")

    def select_buses_by_property(self, prop: str):
        """
        Select the current diagram buses by prop
        :param prop: area, zone, country
        """
        if prop == 'area':
            self.object_select_window = ObjectSelectWindow(title='Area',
                                                           object_list=self.circuit.areas,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:

                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.area == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)

        elif prop == 'country':
            self.object_select_window = ObjectSelectWindow(title='country',
                                                           object_list=self.circuit.countries,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.country == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)

        elif prop == 'zone':
            self.object_select_window = ObjectSelectWindow(title='Zones',
                                                           object_list=self.circuit.zones,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.zone == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)
        else:
            error_msg('Unrecognized option' + str(prop))
            return

    def set_selected_bus_property(self, prop):
        """

        :param prop:
        :return:
        """
        if prop == 'area':
            self.object_select_window = ObjectSelectWindow(title='Area',
                                                           object_list=self.circuit.areas,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_selected_buses():
                    bus.area = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'country':
            self.object_select_window = ObjectSelectWindow(title='country',
                                                           object_list=self.circuit.countries,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_selected_buses():
                    bus.country = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'zone':
            self.object_select_window = ObjectSelectWindow(title='Zones',
                                                           object_list=self.circuit.zones,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_pbj in self.get_selected_buses():
                    bus.zone = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))
        else:
            error_msg('Unrecognized option' + str(prop))
            return

    def default_voltage_change(self):
        """
        When the default voltage changes, update all the diagrams
        """
        val = self.ui.defaultBusVoltageSpinBox.value()

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, DiagramEditorWidget):
                diagram.default_bus_voltage = val

            elif isinstance(diagram, GridMapWidget):
                pass

    def delete_from_all_diagrams(self, elements: List[ALL_DEV_TYPES]):
        """
        Delete elements from all editors
        :param elements: list of devices to delete from the graphics editors
        :return:
        """
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, DiagramEditorWidget):
                diagram_widget.delete_diagram_elements(elements)

            elif isinstance(diagram_widget, GridMapWidget):
                pass

    def search_diagram(self):
        """
        Search elements by name, code or idtag and center them in the screen
        """

        dlg = InputSearchDialogue(deafault_value="",
                                  title="Search",
                                  prompt="Search object by name, code or idtag in the diagram")
        if dlg.exec_():

            if dlg.is_accepted:
                diagram = self.get_selected_diagram_widget()

                if diagram is not None:
                    if isinstance(diagram, DiagramEditorWidget):
                        diagram.graphical_search(search_text=dlg.searchText.lower())

    def show_diagrams_context_menu(self, pos: QtCore.QPoint):
        """
        Show diagrams list view context menu
        :param pos: Relative click position
        """
        context_menu = QtWidgets.QMenu(parent=self.ui.diagramsListView)

        gf.add_menu_entry(menu=context_menu,
                          text="New bus-branch",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.add_complete_bus_branch_diagram)

        gf.add_menu_entry(menu=context_menu,
                          text="New bus-branch from selection",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.new_bus_branch_diagram_from_selection)

        gf.add_menu_entry(menu=context_menu,
                          text="New map",
                          icon_path=":/Icons/icons/map (add).svg",
                          function_ptr=self.add_map_diagram)

        context_menu.addSeparator()
        gf.add_menu_entry(menu=context_menu,
                          text="Remove",
                          icon_path=":/Icons/icons/delete3.svg",
                          function_ptr=self.remove_diagram)

        # Convert global position to local position of the list widget
        mapped_pos = self.ui.diagramsListView.viewport().mapToGlobal(pos)
        context_menu.exec(mapped_pos)

    def disable_all_results_tags(self):
        """
        Disable all tags for the selected diagram
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, DiagramEditorWidget):
            diagram.disable_all_results_tags()

    def enable_all_results_tags(self):
        """
        Enable all tags for the selected diagram
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, DiagramEditorWidget):
            diagram.enable_all_results_tags()
