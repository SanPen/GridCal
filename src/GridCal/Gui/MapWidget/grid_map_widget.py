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
from PySide6.QtWidgets import QSizePolicy, QWidget, QMessageBox
from GridCal.Gui.MapWidget.map_widget import MapWidget, PolylineData, Place
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from GridCal.Engine.Core.Devices.Substation.bus import Bus
from GridCal.Engine.Core.Devices.Branches.line import Line
from GridCal.Engine.Core.Devices.Branches.dc_line import DcLine
from GridCal.Engine.Core.Devices.Branches.transformer import Transformer2W
from GridCal.Engine.Core.Devices.Branches.vsc import VSC
from GridCal.Engine.Core.Devices.Branches.upfc import UPFC
from GridCal.Engine.Core.Devices.Branches.hvdc_line import HvdcLine
from GridCal.Engine.Core.Devices.Branches.transformer3w import Transformer3W
from GridCal.Engine.Core.Devices.Injections.generator import Generator
from GridCal.Engine.Core.Devices.enumerations import DeviceType
from GridCal.Engine.basic_structures import Vec, CxVec, IntVec


class GridMapWidget(MapWidget):

    def __init__(self, parent: Union[QWidget, None], tile_src, start_level: int, name: str):
        MapWidget.__init__(self, parent=parent, tile_src=tile_src, start_level=start_level)

        self.name = name

        # add empty polylines layer
        self.polyline_layer_id = self.AddPolylineLayer(data=[],
                                                       map_rel=True,
                                                       visible=True,
                                                       show_levels=list(range(20)),
                                                       selectable=True,
                                                       # levels at which to show the polylines
                                                       name='<polyline_layer>')

    def setBranchData(self, data):
        self.setLayerData(self.polyline_layer_id, data)
        self.update()

    def colour_results(self,
                       buses: List[Bus],
                       branches: List[Union[Line, DcLine, Transformer2W, Warning, UPFC, VSC]],
                       hvdc_lines: List[HvdcLine],
                       Sbus: CxVec,
                       Sf: CxVec,
                       St: CxVec,
                       voltages: CxVec,
                       loadings: CxVec,
                       types: IntVec = None,
                       losses: CxVec = None,
                       hvdc_Pf: Vec = None,
                       hvdc_Pt: Vec = None,
                       hvdc_losses: Vec = None,
                       hvdc_loading: Vec = None,
                       failed_br_idx: IntVec = None,
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
