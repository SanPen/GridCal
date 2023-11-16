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
from typing import Union, List
import numpy as np
from PySide6.QtWidgets import QWidget
from GridCal.Gui.MapWidget.map_widget import MapWidget, PolylineData, Place
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from GridCalEngine.Core.Devices.Substation import Bus
from GridCalEngine.Core.Devices.Branches.line import Line
from GridCalEngine.Core.Devices.Branches.dc_line import DcLine
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Core.Devices.Branches.vsc import VSC
from GridCalEngine.Core.Devices.Branches.upfc import UPFC
from GridCalEngine.Core.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Core.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCal.Gui.MapWidget.Tiles.tiles import Tiles


class GridMapWidget(MapWidget):

    def __init__(self,
                 parent: Union[QWidget, None],
                 tile_src: Tiles,
                 start_level: int,
                 longitude: float,
                 latitude: float,
                 name: str,
                 diagram: Union[None, MapDiagram] = None):

        MapWidget.__init__(self,
                           parent=parent,
                           tile_src=tile_src,
                           start_level=start_level,
                           zoom_callback=self.zoom_callback,
                           position_callback=self.position_callback)

        # diagram to store the objects locations
        self.diagram: MapDiagram = MapDiagram(name=name,
                                              tile_source=tile_src.TilesetName,
                                              start_level=start_level,
                                              longitude=longitude,
                                              latitude=latitude) if diagram is None else diagram

        # add empty polylines layer
        self.polyline_layer_id = self.AddPolylineLayer(data=[],
                                                       map_rel=True,
                                                       visible=True,
                                                       show_levels=list(range(20)),
                                                       selectable=True,
                                                       # levels at which to show the polylines
                                                       name='<polyline_layer>')

        self.GotoLevelAndPosition(level=start_level, longitude=longitude, latitude=latitude)

    def set_diagram(self, diagram: MapDiagram):
        """

        :param diagram:
        :return:
        """
        self.diagram = diagram

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

    def setBranchData(self, data):
        """

        :param data:
        """
        self.setLayerData(self.polyline_layer_id, data)
        self.update()

    def zoom_callback(self, zoom_level: int) -> None:
        """

        :param zoom_level:
        :return:
        """
        # print('zoom', zoom_level)
        self.diagram.start_level = zoom_level

    def position_callback(self, longitude: float, latitude: float) -> None:
        """

        :param longitude:
        :param latitude:
        :return:
        """
        # print('Map lat:', latitude, 'lon:', longitude)
        self.diagram.latitude = latitude
        self.diagram.longitude = longitude

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

        # (polyline_points, placement, width, rgba, offset_x, offset_y, udata)
        data: List[PolylineData] = list()

        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()
        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage']

        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = np.abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng

        n = len(buses)
        longitudes = np.zeros(n)
        latitudes = np.zeros(n)
        nodes_dict = dict()
        for i, bus in enumerate(buses):
            longitudes[i] = bus.longitude
            latitudes[i] = bus.latitude
            nodes_dict[bus.name] = (bus.latitude, bus.longitude)

        # Pnorm = np.abs(Sbus.real) / np.max(Sbus.real)
        #
        # add node positions
        # for i, bus in enumerate(circuit.buses):
        #
        #     tooltip = str(i) + ': ' + bus.name + '\n' \
        #               + 'V:' + "{:10.4f}".format(vabs[i]) + " <{:10.4f}".format(vang[i]) + 'º [p.u.]\n' \
        #               + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [kV]'
        #     if Sbus is not None:
        #         tooltip += '\nS: ' + "{:10.4f}".format(Sbus[i] * Sbase) + ' [MVA]'
        #     if types is not None:
        #         tooltip += '\nType: ' + bus_types[types[i]]
        #
        #     # get the line colour
        #     r, g, b, a = voltage_cmap(vnorm[i])
        #     color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
        #     html_color = color.name()
        #
        #     if use_flow_based_width:
        #         radius = int(np.floor(min_bus_width + Pnorm[i] * (max_bus_width - min_bus_width)))
        #     else:
        #         radius = 50
        #
        #     position = bus.get_coordinates()
        #     html = '<i>' + tooltip + '</i>'
        #     folium.Circle(position,
        #                   popup=html,
        #                   radius=radius,
        #                   color=html_color,
        #                   tooltip=tooltip).add_to(marker_cluster)

        # add lines
        lnorm = np.abs(loadings)
        lnorm[lnorm == np.inf] = 0
        Sfabs = np.abs(Sf)
        Sfnorm = Sfabs / np.max(Sfabs + 1e-20)
        for i, branch in enumerate(branches):

            points = branch.get_coordinates()

            if not viz.has_null_coordinates(points):
                # compose the tooltip
                tooltip = str(i) + ': ' + branch.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                if Sf is not None:
                    tooltip += '\nPower: ' + "{:10.4f}".format(Sf[i]) + ' [MVA]'
                if losses is not None:
                    tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'

                # get the line colour
                a = 255
                if cmap == palettes.Colormaps.Green2Red:
                    b, g, r = palettes.green_to_red_bgr(lnorm[i])

                elif cmap == palettes.Colormaps.Heatmap:
                    b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                elif cmap == palettes.Colormaps.TSO:
                    b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(), lnorm[i])

                else:
                    r, g, b, a = loading_cmap(lnorm[i])
                    r *= 255
                    g *= 255
                    b *= 255
                    a *= 255

                if use_flow_based_width:
                    weight = int(np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                else:
                    weight = 3

                # draw the line
                data.append(PolylineData(points, Place.Center, weight, (r, g, b, a), 0, 0, {}))

        if len(hvdc_lines) > 0:

            lnorm = np.abs(hvdc_loading)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(hvdc_Pf)
            Sfnorm = Sfabs / np.max(Sfabs)

            for i, branch in enumerate(hvdc_lines):

                points = branch.get_coordinates()

                if not viz.has_null_coordinates(points):
                    # compose the tooltip
                    tooltip = str(i) + ': ' + branch.name
                    tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                    if Sf is not None:
                        tooltip += '\nPower: ' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'
                    if losses is not None:
                        tooltip += '\nLosses: ' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'

                    # get the line colour
                    a = 255
                    if cmap == palettes.Colormaps.Green2Red:
                        b, g, r = palettes.green_to_red_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.Heatmap:
                        b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.TSO:
                        b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(), lnorm[i])

                    else:
                        r, g, b, a = loading_cmap(lnorm[i])
                        r *= 255
                        g *= 255
                        b *= 255
                        a *= 255

                    if use_flow_based_width:
                        weight = int(np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                    else:
                        weight = 3

                    # draw the line
                    # data.append((points, {"width": weight, "color": html_color, 'tooltip': tooltip}))
                    data.append(PolylineData(points, Place.Center, weight, (r, g, b, a), 0, 0, {}))

        self.setLayerData(lid=self.polyline_layer_id, data=data)
        self.update()
