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
import os
from typing import List, Tuple, Union

import networkx as nx
import numpy as np
import pandas as pd
import qdarktheme
from PySide6 import QtGui, QtWidgets, QtCore
from matplotlib import pyplot as plt
from pandas.plotting import register_matplotlib_converters

import GridCalEngine.Core.Devices as dev
import GridCalEngine.Simulations as sim
import GridCal.Gui.GuiFunctions as gf
import GridCal.Gui.Visualization.palettes as palettes
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCal.Gui.GeneralDialogues import LogsDialogue, CheckListDialogue
from GridCal.Gui.BusViewer.bus_viewer_dialogue import BusViewerGUI
from GridCal.Gui.GridEditorWidget import GridEditorWidget, generate_bus_branch_diagram
from GridCal.Gui.MapWidget.grid_map_widget import GridMapWidget
from GridCal.Gui.messages import yes_no_question, error_msg, info_msg
from GridCal.Gui.Main.gui_sub_classes.compiled_arrays import CompiledArraysMain
from GridCal.Gui.Main.object_select_window import ObjectSelectWindow
from GridCal.Gui.MapWidget.TileProviders.blue_marble import BlueMarbleTiles
from GridCal.Gui.MapWidget.TileProviders.cartodb import CartoDbTiles



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
        self.diagram_widgets_list: List[Union[GridEditorWidget, BusViewerGUI, GridMapWidget]] = list()

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
        self.layout_algorithms_dict['graphviz_neato'] = nx.nx_agraph.graphviz_layout
        self.layout_algorithms_dict['graphviz_dot'] = nx.nx_agraph.graphviz_layout
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
        self.ui.actionAdd_selected_to_contingency.triggered.connect(self.add_selected_to_contingency)
        self.ui.actionAdd_selected_as_new_investment.triggered.connect(self.add_selected_to_investment)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out)
        self.ui.actionAdd_general_bus_branch_diagram.triggered.connect(self.add_bus_branch_diagram)
        self.ui.actionAdd_selection_bus_branch_diagram.triggered.connect(self.add_selection_bus_branch_diagram)
        self.ui.actionAdd_bus_vecinity_diagram.triggered.connect(self.add_bus_vecinity_diagram_from_diagram_selection)
        self.ui.actionAdd_map.triggered.connect(self.add_map_diagram)
        self.ui.actionAdd_substation_diagram.triggered.connect(self.add_substation_diagram)
        self.ui.actionRemove_selected_diagram.triggered.connect(self.remove_diagram)
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)
        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)
        self.ui.actionCenter_view.triggered.connect(self.center_nodes)
        self.ui.actionAutoatic_layout.triggered.connect(self.auto_layout)

        # Buttons
        self.ui.colour_results_pushButton.clicked.connect(self.colour_diagrams)
        self.ui.view_previous_simulation_step_pushButton.clicked.connect(self.colour_previous_simulation_step)
        self.ui.view_next_simulation_step_pushButton.clicked.connect(self.colour_next_simulation_step)
        self.ui.busViewerButton.clicked.connect(self.add_bus_vecinity_diagram_from_model)

        # list clicks
        self.ui.diagramsListView.clicked.connect(self.set_selected_diagram_on_click)

        # combobox change
        self.ui.plt_style_comboBox.currentTextChanged.connect(self.plot_style_change)
        self.ui.available_results_to_color_comboBox.currentTextChanged.connect(self.update_available_steps_to_color)

        # sliders
        self.ui.profile_start_slider.valueChanged.connect(self.profile_sliders_changed)
        self.ui.profile_end_slider.valueChanged.connect(self.profile_sliders_changed)
        self.ui.simulation_results_step_slider.valueChanged.connect(self.diagrams_time_slider_change)

        # spinbox change
        self.ui.explosion_factor_doubleSpinBox.valueChanged.connect(self.explosion_factor_change)

        # check boxes
        self.ui.dark_mode_checkBox.clicked.connect(self.change_theme_mode)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

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
            graph = self.circuit.build_graph()

            sel = self.ui.automatic_layout_comboBox.currentText()
            pos_alg = self.layout_algorithms_dict[sel]

            # get the positions of a spring layout of the graph
            if sel == 'random_layout':
                pos = pos_alg(graph)
            elif sel == 'spring_layout':
                pos = pos_alg(graph, iterations=100, scale=10)
            elif sel == 'graphviz_neato':
                pos = pos_alg(graph, prog='neato')
            elif sel == 'graphviz_dot':
                pos = pos_alg(graph, prog='dot')
            else:
                pos = pos_alg(graph, scale=10)

            diagram_widget = self.get_selected_diagram_widget()

            if diagram_widget:
                if isinstance(diagram_widget, GridEditorWidget):

                    # assign the positions to the graphical objects of the nodes
                    for i, bus in enumerate(self.circuit.buses):
                        x = pos[i][0] * 500
                        y = pos[i][1] * 500
                        position = diagram_widget.diagram.query_point(bus)

                        if position:
                            if position.graphic_object:
                                position.graphic_object.setPos(QtCore.QPoint(x, y))
                                position.x = x
                                position.y = y

                    # adjust the view
                    diagram_widget.center_nodes()

        else:
            pass  # asked and decided ot to change the layout

    def bigger_nodes(self):
        """
        Move the nodes more separated
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):
                diagram.expand_node_distances()

    def smaller_nodes(self):
        """
        Move the nodes closer
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):
                diagram.shrink_node_distances()

    def center_nodes(self):
        """
        Center the nodes in the screen
        """

        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):
                selected = self.get_selected_buses()

                if len(selected) == 0:
                    buses = self.circuit.buses
                else:
                    buses = [b for i, b in selected]

                diagram.center_nodes(buses=buses)

    def get_selected_buses(self) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        # TODO: reformulate this
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.circuit.buses):
            if bus.graphic_obj is not None:
                if bus.graphic_obj.isSelected():
                    lst.append((k, bus))
        return lst

    def explosion_factor_change(self):
        """
        Change the node explosion factor
        """
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, GridEditorWidget):
                diagram.expand_factor = self.ui.explosion_factor_doubleSpinBox.value()

    def adjust_all_node_width(self):
        """
        Adapt the width of all the nodes to their names
        """
        for bus in self.circuit.buses:
            if bus.graphic_obj is not None:
                bus.graphic_obj.adapt()

    def zoom_in(self):
        """
        Zoom the diagram in
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):
                diagram.editor_graphics_view.zoom_in()

    def zoom_out(self):
        """
        Zoom the diagram out
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):
                diagram.editor_graphics_view.zoom_out()

    def profile_sliders_changed(self):
        """
        Correct sliders if they change
        """
        start = self.ui.profile_start_slider.value()
        end = self.ui.profile_end_slider.value()

        if start > end:
            self.ui.profile_end_slider.setValue(start)
            end = start

        if self.circuit.time_profile is not None:
            if len(self.circuit.time_profile) > 0:
                t1 = self.circuit.time_profile[start]
                t2 = self.circuit.time_profile[end]
                t1 = pd.to_datetime(t1).strftime('%d/%m/%Y %H:%M')
                t2 = pd.to_datetime(t2).strftime('%d/%m/%Y %H:%M')
                self.ui.start_label.setText(str(t1))
                self.ui.end_label.setText(str(t2) + ' [{0}]'.format(end - start))

    def grid_colour_function(self, plot_function, current_study: str, current_step: int) -> None:
        """
        Colour the schematic or the map
        :param plot_function: function pointer to the function doing the plotting
        :param current_study: current_study name
        :param current_step: current time step
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

        elif current_study == sim.PowerFlowTimeSeriesDriver.tpe.value:
            results: sim.PowerFlowTimeSeriesResults = self.session.get_results(sim.SimulationTypes.TimeSeries_run)
            bus_active = [bus.active_prof[current_step] for bus in self.circuit.buses]
            br_active = [br.active_prof[current_step] for br in self.circuit.get_branches_wo_hvdc()]
            hvdc_active = [hvdc.active_prof[current_step] for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 Sbus=results.S[current_step, :],
                                 bus_active=bus_active,
                                 Sf=results.Sf[current_step, :],
                                 St=results.St[current_step, :],
                                 voltages=results.voltage[current_step, :],
                                 loadings=np.abs(results.loading[current_step, :]),
                                 types=results.bus_types,
                                 losses=results.losses[current_step, :],
                                 br_active=br_active,
                                 hvdc_Pf=results.hvdc_Pf[current_step, :],
                                 hvdc_Pt=results.hvdc_Pt[current_step, :],
                                 hvdc_losses=results.hvdc_losses[current_step, :],
                                 hvdc_loading=results.hvdc_loading[current_step, :],
                                 hvdc_active=hvdc_active,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width,
                                 cmap=cmap)

        elif current_study == sim.ContinuationPowerFlowDriver.tpe.value:
            results: sim.ContinuationPowerFlowResults = self.session.get_results(sim.SimulationTypes.ContinuationPowerFlow_run)
            bus_active = [bus.active for bus in self.circuit.buses]
            br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 Sbus=results.Sbus[current_step, :],
                                 bus_active=bus_active,
                                 Sf=results.Sf[current_step, :],
                                 St=results.St[current_step, :],
                                 voltages=results.voltages[current_step, :],
                                 types=results.bus_types,
                                 loadings=np.abs(results.loading[current_step, :]),
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

        elif current_study == sim.StochasticPowerFlowDriver.tpe.value:
            results: sim.StochasticPowerFlowResults = self.session.get_results(sim.SimulationTypes.StochasticPowerFlow)
            bus_active = [bus.active for bus in self.circuit.buses]
            br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
            # hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 Sbus=results.S_points[current_step, :],
                                 types=results.bus_types,
                                 voltages=results.V_points[current_step, :],
                                 bus_active=bus_active,
                                 loadings=np.abs(results.loading_points[current_step, :]),
                                 Sf=results.Sbr_points[current_step, :],
                                 St=-results.Sbr_points[current_step, :],
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

        elif current_study == sim.ShortCircuitDriver.tpe.value:
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

        elif current_study == sim.OptimalPowerFlowDriver.tpe.value:
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

        elif current_study == sim.OptimalPowerFlowTimeSeriesDriver.tpe.value:
            results: sim.OptimalPowerFlowTimeSeriesResults = self.session.get_results(sim.SimulationTypes.OPFTimeSeries_run)
            bus_active = [bus.active_prof[current_step] for bus in self.circuit.buses]
            br_active = [br.active_prof[current_step] for br in self.circuit.get_branches_wo_hvdc()]
            hvdc_active = [hvdc.active_prof[current_step] for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 voltages=results.voltage[current_step, :],
                                 Sbus=results.Sbus[current_step, :],
                                 types=results.bus_types,
                                 bus_active=bus_active,
                                 Sf=results.Sf[current_step, :],
                                 St=results.St[current_step, :],
                                 loadings=np.abs(results.loading[current_step, :]),
                                 br_active=br_active,
                                 hvdc_Pf=results.hvdc_Pf[current_step, :],
                                 hvdc_Pt=-results.hvdc_Pf[current_step, :],
                                 hvdc_loading=results.hvdc_loading[current_step, :],
                                 hvdc_active=hvdc_active,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width,
                                 cmap=cmap)

        elif current_study == sim.LinearAnalysisDriver.tpe.value:
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

        elif current_study == sim.LinearAnalysisTimeSeriesDriver.tpe.value:
            results: sim.LinearAnalysisTimeSeriesResults = self.session.get_results(sim.SimulationTypes.LinearAnalysis_TS_run)
            bus_active = [bus.active_prof[current_step] for bus in self.circuit.buses]
            br_active = [br.active_prof[current_step] for br in self.circuit.get_branches_wo_hvdc()]
            hvdc_active = [hvdc.active_prof[current_step] for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 Sbus=results.S[current_step],
                                 voltages=results.voltage[current_step],
                                 types=results.bus_types,
                                 bus_active=bus_active,
                                 Sf=results.Sf[current_step],
                                 St=-results.Sf[current_step],
                                 loadings=np.abs(results.loading[current_step]),
                                 br_active=br_active,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width,
                                 cmap=cmap)

        elif current_study == sim.ContingencyAnalysisDriver.tpe.value:
            results: sim.ContingencyAnalysisResults = self.session.get_results(sim.SimulationTypes.ContingencyAnalysis_run)
            bus_active = [bus.active for bus in self.circuit.buses]
            br_active = [br.active for br in self.circuit.get_branches_wo_hvdc()]
            hvdc_active = [hvdc.active for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 Sbus=results.Sbus[current_step, :],
                                 voltages=results.voltage[current_step, :],
                                 types=results.bus_types,
                                 bus_active=bus_active,
                                 Sf=results.Sf[current_step, :],
                                 St=-results.Sf[current_step, :],
                                 loadings=np.abs(results.loading[current_step, :]),
                                 br_active=br_active,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width,
                                 cmap=cmap)

        elif current_study == sim.ContingencyAnalysisTimeSeries.tpe.value:
            results: sim.ContingencyAnalysisTimeSeriesResults = self.session.get_results(sim.SimulationTypes.ContingencyAnalysisTS_run)
            bus_active = [bus.active_prof[current_step] for bus in self.circuit.buses]
            br_active = [br.active_prof[current_step] for br in self.circuit.get_branches_wo_hvdc()]
            hvdc_active = [hvdc.active_prof[current_step] for hvdc in self.circuit.hvdc_lines]

            return plot_function(buses=buses,
                                 branches=branches,
                                 hvdc_lines=hvdc_lines,
                                 voltages=np.ones(results.nbus, dtype=complex),
                                 Sbus=results.S[current_step, :],
                                 types=results.bus_types,
                                 bus_active=bus_active,
                                 Sf=results.worst_flows[current_step, :],
                                 St=-results.worst_flows[current_step, :],
                                 loadings=np.abs(results.worst_loading[current_step]),
                                 br_active=br_active,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width,
                                 cmap=cmap)

        elif current_study == sim.InputsAnalysisDriver.tpe.value:

            results = self.session.get_results(sim.SimulationTypes.InputsAnalysis_run)
            nbus = self.circuit.get_bus_number()
            nbr = self.circuit.get_branch_number()
            bus_active = [bus.active_prof[current_step] for bus in self.circuit.buses]
            br_active = [br.active_prof[current_step] for br in self.circuit.get_branches_wo_hvdc()]

            # empty
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

        elif current_study == sim.AvailableTransferCapacityTimeSeriesDriver.tpe.value:
            pass

        elif current_study == sim.AvailableTransferCapacityDriver.tpe.value:
            pass

        elif current_study == 'Transient stability':
            raise Exception('Not implemented :(')

        else:
            print('<' + current_study + '> Not implemented :(')

    def colour_diagrams(self) -> None:
        """
        Color the grid now
        """

        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:
            current_study = self.ui.available_results_to_color_comboBox.currentText()
            current_step = self.ui.simulation_results_step_slider.value()

            for diagram in self.diagram_widgets_list:

                if isinstance(diagram, GridEditorWidget):
                    self.grid_colour_function(plot_function=diagram.colour_results,
                                              current_study=current_study,
                                              current_step=current_step)

                elif isinstance(diagram, GridMapWidget):
                    self.grid_colour_function(plot_function=diagram.colour_results,
                                              current_study=current_study,
                                              current_step=current_step)

    def set_diagrams_list_view(self) -> None:
        """
        Create the diagrams list view
        """
        mdl = gf.DiagramsModel(self.diagram_widgets_list)
        self.ui.diagramsListView.setModel(mdl)

    def get_selected_diagram_widget(self) -> Union[None, GridEditorWidget, GridMapWidget, BusViewerGUI]:
        """
        Get the currently selected diagram
        :return: None, GridEditorWidget, GridMapWidget, BusViewerGUI
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

            if isinstance(diagram_widget, GridEditorWidget):
                # set pointer to the circuit
                diagram = generate_bus_branch_diagram(buses=self.circuit.buses,
                                                      lines=self.circuit.lines,
                                                      dc_lines=self.circuit.dc_lines,
                                                      transformers2w=self.circuit.transformers2w,
                                                      transformers3w=self.circuit.transformers3w,
                                                      hvdc_lines=self.circuit.hvdc_lines,
                                                      vsc_devices=self.circuit.vsc_devices,
                                                      upfc_devices=self.circuit.upfc_devices,
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

    def add_bus_branch_diagram(self) -> None:
        """
        Add ageneral bus-branch diagram
        """
        diagram = generate_bus_branch_diagram(buses=self.circuit.buses,
                                              lines=self.circuit.lines,
                                              dc_lines=self.circuit.dc_lines,
                                              transformers2w=self.circuit.transformers2w,
                                              transformers3w=self.circuit.transformers3w,
                                              hvdc_lines=self.circuit.hvdc_lines,
                                              vsc_devices=self.circuit.vsc_devices,
                                              upfc_devices=self.circuit.upfc_devices,
                                              explode_factor=1.0,
                                              prog_func=None,
                                              text_func=None,
                                              name='All bus branches')
        diagram_widget = GridEditorWidget(circuit=self.circuit, diagram=diagram)
        diagram_widget.setStretchFactor(1, 10)
        diagram_widget.center_nodes()
        self.add_diagram(diagram_widget)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram_widget)

    def add_selection_bus_branch_diagram(self):
        """
        Add a bus-branch diagram of a particular area
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:

            if isinstance(diagram_widget, GridEditorWidget):
                diagram = diagram_widget.get_selection_diagram()
                self.add_diagram(GridEditorWidget(self.circuit, diagram=diagram))
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
                        diagram = BusViewerGUI(circuit=self.circuit,
                                               root_bus=root_bus,
                                               name=root_bus.name + ' vecinity',
                                               view_toolbar=False)
                        self.add_diagram(diagram)
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
                diagram_widget = GridEditorWidget(self.circuit, diagram=diagram)
                diagram_widget.setStretchFactor(1, 10)
                diagram_widget.center_nodes()
                self.diagram_widgets_list.append(diagram_widget)

            elif isinstance(diagram, dev.MapDiagram):
                # select the tile source
                tile_source = self.tile_sources[self.ui.tile_provider_comboBox.currentText()]

                # create the map widget
                map_widget = GridMapWidget(parent=None,
                                           tile_src=tile_source,
                                           start_level=5,
                                           name='Map diagram')
                map_widget.GotoLevelAndPosition(5, -15.41, 40.11)
                self.diagram_widgets_list.append(map_widget)

            elif isinstance(diagram, dev.NodeBreakerDiagram):
                print("NodeBreakerDiagram not implemented yet :/")

            else:
                raise Exception("Unknown diagram type")

        self.set_diagrams_list_view()

    def add_bus_vecinity_diagram_from_diagram_selection(self):
        """
        Add a bus vecinity diagram
        :return:
        """

        sel_buses = self.get_selected_buses()

        if len(sel_buses):
            bus_idx, root_bus = sel_buses[0]
            diagram = BusViewerGUI(circuit=self.circuit,
                                   root_bus=root_bus,
                                   name=root_bus.name + ' vecinity',
                                   view_toolbar=False)
            self.add_diagram(diagram)
            self.set_diagrams_list_view()

    def add_map_diagram(self) -> None:
        """
        Adds a Map diagram
        """
        # select the tile source
        tile_source = self.tile_sources[self.ui.tile_provider_comboBox.currentText()]

        # create the map widget
        map_widget = GridMapWidget(parent=None,
                                   tile_src=tile_source,
                                   start_level=5,
                                   name='Map diagram')
        map_widget.GotoLevelAndPosition(5, -15.41, 40.11)

        self.add_diagram(map_widget)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram=map_widget)

    def add_substation_diagram(self):
        """
        Add substation diagram
        """
        self.set_diagrams_list_view()

    def add_diagram(self, diagram_widget: Union[GridEditorWidget, GridMapWidget, BusViewerGUI]):
        """
        Add diagram
        :param diagram_widget:
        :return:
        """

        # add the widget pointer
        self.diagram_widgets_list.append(diagram_widget)

        # add the diagram to the circuit
        self.circuit.diagrams.append(diagram_widget.diagram)

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

    def set_diagram_widget(self, diagram: Union[GridEditorWidget, GridMapWidget, BusViewerGUI]):
        """
        Set the current diagram in the container
        :param diagram: GridEditorWidget, GridMapWidget, BusViewerGUI
        """
        self.remove_all_diagram_widgets()

        # add the new diagram
        self.ui.schematic_layout.addWidget(diagram)

        # set the alignment
        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 2)

        # set the selected index
        row = self.diagram_widgets_list.index(diagram)
        index = self.ui.diagramsListView.model().index(row, 0)
        self.ui.diagramsListView.setCurrentIndex(index)

    def change_theme_mode(self) -> None:
        """
        Change the GUI theme
        :return:
        """
        custom_colors = {"primary": "#00aa88ff",
                         "primary>list.selectionBackground": "#00aa88be"}

        if self.ui.dark_mode_checkBox.isChecked():
            qdarktheme.setup_theme(theme='dark', custom_colors=custom_colors)

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, GridEditorWidget):
                    diagram.set_dark_mode()

            self.colour_diagrams()
        else:
            qdarktheme.setup_theme(theme='light', custom_colors=custom_colors)

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, GridEditorWidget):
                    diagram.set_light_mode()

            self.colour_diagrams()

    def plot_style_change(self):
        """
        Change the style
        """
        style = self.ui.plt_style_comboBox.currentText()
        plt.style.use(style)

    def diagrams_time_slider_change(self) -> None:
        """
        On change of the schematic slider...
        """
        idx = self.ui.simulation_results_step_slider.value()

        if len(self.schematic_list_steps):
            if idx > -1:
                self.ui.schematic_step_label.setText(self.schematic_list_steps[idx])
        else:
            self.ui.schematic_step_label.setText("No steps")

    def export_diagram(self):
        """
        Save the schematic
        :return:
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, GridEditorWidget):

                # declare the allowed file types
                files_types = "Scalable Vector Graphics (*.svg);;Portable Network Graphics (*.png)"

                fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

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
            if yes_no_question("All nodes will be positioned to a 2D plane projection of their latitude and longitude. "
                               "Are you sure of this?"):
                logger = self.circuit.fill_xy_from_lat_lon(destructive=True, factor=0.01, remove_offset=True)

                if len(logger) > 0:
                    dlg = LogsDialogue('Set xy from lat lon', logger)
                    dlg.exec_()

                self.redraw_current_diagram()

    @staticmethod
    def set_big_bus_marker(buses, color: QtGui.QColor):
        """
        Set a big marker at the selected buses
        :param buses: list of Bus objects
        :param color: colour to use
        """
        for bus in buses:
            if bus.graphic_obj is not None:
                bus.graphic_obj.add_big_marker(color=color)
                bus.graphic_obj.setSelected(True)

    def delete_selected_from_the_schematic(self):
        """
        Prompt to delete the selected buses from the schematic
        """
        if len(self.circuit.buses) > 0:

            # get the selected buses
            selected = self.get_selected_buses()

            if len(selected) > 0:
                reply = QtWidgets.QMessageBox.question(self, 'Delete',
                                                       'Are you sure that you want to delete the selected elements?',
                                                       QtWidgets.QMessageBox.StandardButton.Yes,
                                                       QtWidgets.QMessageBox.StandardButton.No)

                if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:

                    # remove the buses (from the schematic and the circuit)
                    for k, bus in selected:
                        if bus.graphic_obj is not None:
                            # this is a more complete function than the circuit one because it removes the
                            # graphical items too, and for loads and generators it deletes them properly
                            bus.graphic_obj.remove(ask=False)
                else:
                    pass
            else:
                info_msg('Choose some elements from the schematic', 'Delete buses')
        else:
            pass

    def try_to_fix_buses_location(self):
        """
        Try to fix the location of the buses
        """

        selected_buses = self.get_selected_buses()
        if len(selected_buses) > 0:
            self.circuit.try_to_fix_buses_location(buses_selection=selected_buses)
            for k, bus in selected_buses:
                if bus.graphic_obj is not None:
                    bus.graphic_obj.set_position(x=bus.x, y=bus.y)
        else:
            info_msg('Choose some elements from the schematic', 'Fix buses locations')

    def colour_next_simulation_step(self):
        """
        Next colour step
        """
        current_step = self.ui.simulation_results_step_slider.value()
        count = self.ui.simulation_results_step_slider.maximum() + 1

        if count > 0:
            nxt = current_step + 1

            if nxt >= count:
                nxt = count - 1

            self.ui.simulation_results_step_slider.setValue(nxt)

            self.colour_diagrams()

    def colour_previous_simulation_step(self):
        """
        Prev colour step
        """
        current_step = self.ui.simulation_results_step_slider.value()
        count = self.ui.simulation_results_step_slider.maximum() + 1

        if count > 0:
            prv = current_step - 1

            if prv < 0:
                prv = 0

            self.ui.simulation_results_step_slider.setValue(prv)

            self.colour_diagrams()

    def update_available_steps_to_color(self):
        """
        Update the available simulation steps in the combo box
        """
        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:
            current_study = self.ui.available_results_to_color_comboBox.currentText()

            self.schematic_list_steps = self.available_results_steps_dict[current_study]

            if len(self.schematic_list_steps) > 0:
                self.ui.simulation_results_step_slider.setMinimum(0)
                self.ui.simulation_results_step_slider.setMaximum(len(self.schematic_list_steps) - 1)
                self.ui.simulation_results_step_slider.setSliderPosition(0)
                self.ui.schematic_step_label.setText(self.schematic_list_steps[0])
            else:
                self.ui.simulation_results_step_slider.setMinimum(0)
                self.ui.simulation_results_step_slider.setMaximum(0)
                self.ui.simulation_results_step_slider.setSliderPosition(0)
                self.ui.schematic_step_label.setText("No steps")

    def get_selected_contingency_devices(self) -> List[dev.EditableDevice]:
        """
        Get the selected buses
        :return:
        """
        lst: List[dev.EditableDevice] = list()
        for k, elm in enumerate(self.circuit.get_contingency_devices()):
            if elm.graphic_obj is not None:
                if elm.graphic_obj.isSelected():
                    lst.append(elm)
        return lst

    def get_selected_investment_devices(self) -> List[dev.EditableDevice]:
        """
        Get the selected investment devices
        :return:
        """
        lst: List[dev.EditableDevice] = list()
        for k, elm in enumerate(self.circuit.get_investment_devices()):
            if elm.graphic_obj is not None:
                if elm.graphic_obj.isSelected():
                    lst.append(elm)
        return lst

    def add_selected_to_contingency(self):
        """
        Add contingencies from the schematic selection
        """
        if len(self.circuit.buses) > 0:

            # get the selected buses
            selected = self.get_selected_contingency_devices()

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
            selected = self.get_selected_investment_devices()

            if len(selected) > 0:
                names = [elm.type_name + ": " + elm.name for elm in selected]
                self.investment_checks_diag = CheckListDialogue(objects_list=names, title="Add investment")
                self.investment_checks_diag.setModal(True)
                self.investment_checks_diag.exec_()

                if self.investment_checks_diag.is_accepted:

                    group = dev.InvestmentsGroup(idtag=None,
                                                 name="Investment " + str(len(self.circuit.contingency_groups)),
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_investments_group(group)

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

    def set_selected_bus_property(self, prop):
        """

        :param prop:
        :return:
        """
        if prop == 'area':
            self.object_select_window = ObjectSelectWindow('Area', self.circuit.areas, parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus in self.get_selected_buses():
                    bus.area = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'country':
            self.object_select_window = ObjectSelectWindow('country', self.circuit.countries, parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus in self.get_selected_buses():
                    bus.country = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'zone':
            self.object_select_window = ObjectSelectWindow('Zones', self.circuit.zones)
            self.object_select_window.setModal(True)
            self.object_select_window.exec_()

            if self.object_select_window.selected_object is not None:
                for k, bus in self.get_selected_buses():
                    bus.zone = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))
        else:
            error_msg('Unrecognized option' + str(prop))
            return
