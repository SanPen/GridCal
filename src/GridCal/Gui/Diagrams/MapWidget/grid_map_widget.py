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
from typing import Union, List, Tuple
import numpy as np
from PySide6.QtWidgets import QWidget, QGraphicsItem
from collections.abc import Callable

from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.Devices.Diagrams.base_diagram import PointsGroup
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Branches.line_locations import LineLocation

from GridCal.Gui.Diagrams.MapWidget.Schema.map_template_line import MapTemplateLine
from GridCal.Gui.Diagrams.MapWidget.Schema.node_graphic_item import NodeGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Schema.segment import Segment
from GridCal.Gui.Diagrams.MapWidget.Schema.substation_graphic_item import SubstationGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Schema.voltage_level_graphic_item import VoltageLevelGraphicItem
from GridCal.Gui.Diagrams.MapWidget.map_widget import MapWidget, PolylineData, Place
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from GridCal.Gui.Diagrams.graphics_manager import GraphicsManager
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles


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

        self.Substations = list()
        self.devX = 48.3
        self.devY = 61.9

        # object to handle the relation between the graphic widgets and the database objects
        self.graphics_manager = GraphicsManager()

        # diagram to store the DB objects locations
        self.diagram: MapDiagram = MapDiagram(name=name,
                                              tile_source=tile_src.TilesetName,
                                              start_level=start_level,
                                              longitude=longitude,
                                              latitude=latitude) if diagram is None else diagram

        # draw
        self.draw()

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

    def delete_diagram_element(self, device: ALL_DEV_TYPES):
        # TODO: Implement this
        pass

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

    def add_to_scene(self, graphic_object: QGraphicsItem = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """

        self.diagram_scene.addItem(graphic_object)

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

    def to_lat_lon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert x, y position in the map to latitude and longitude
        :param x:
        :param y:
        :return:
        """

        # transform = 180 / np.pi
        # lat = np.degrees(2 * np.arctan(np.exp(y / (self.devY * transform))) - np.pi / 2)
        # lon = np.degrees(x / (self.devX * transform))

        # lon, lat = self.view_to_geo(xview=x, yview=y)

        lat = - y / self.devY
        lon = x / self.devX
        return lat, lon

    def to_x_y(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return:
        """
        # transform = 180 / np.pi
        # lat_rad = np.radians(lat)
        # y = -self.devY * transform * np.log(np.tan(np.pi / 4 + lat_rad / 2))
        # x = self.devX * transform * np.radians(lon)

        x = lon * self.devX
        y = -lat * self.devY

        # x, y = self.geo_to_view(longitude=lon, latitude=lat)

        return x, y

    def update_diagram_element(self,
                               device: ALL_DEV_TYPES,
                               latitude: float = 0.0,
                               longitude: float = 0.0,
                               altitude: float = 0.0,
                               graphic_object: QGraphicsItem = None) -> None:
        """
        Set the position of a device in the diagram
        :param device: EditableDevice
        :param latitude:
        :param longitude:
        :param altitude:
        :param graphic_object: Graphic object associated
        """
        self.diagram.set_point(device=device,
                               location=MapLocation(latitude=latitude,
                                                    longitude=longitude,
                                                    altitude=altitude,
                                                    api_object=device))

        self.graphics_manager.add_device(elm=device, graphic=graphic_object)

    def create_node(self,
                    line_container: MapTemplateLine,
                    api_object: LineLocation,
                    lat: float, lon: float) -> NodeGraphicItem:
        """

        :param line_container:
        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = NodeGraphicItem(editor=self,
                                         line_container=line_container,
                                         api_object=api_object,
                                         lat=lat, lon=lon,
                                         r=0.005)
        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        line_container.add_node(node=graphic_object)

        return graphic_object

    def create_line(self, api_object: BRANCH_TYPES, diagram: MapDiagram) -> MapTemplateLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :param diagram: MapDiagram instance
        :return: MapTemplateLine
        """
        line_container = MapTemplateLine(editor=self, api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        diagram_locations: PointsGroup = diagram.data.get(DeviceType.LineLocation.value, None)

        # create the nodes
        for elm in api_object.locations.data:

            if diagram_locations is None:
                # no locations found, use the data from the api object
                # lat = elm.lat
                # lon = elm.long
                pass
            else:

                # try to get location from the diagram
                diagram_location = diagram_locations.locations.get(elm.idtag, None)

                if diagram_location is None:
                    # no particular location found, use the data from the api object
                    # lat = elm.lat
                    # lon = elm.long
                    pass
                else:
                    # Draw only what's on the diagram
                    # diagram data found, use it
                    lat = diagram_location.latitude
                    lon = diagram_location.longitude

                    graphic_obj = self.create_node(line_container=line_container,
                                                   api_object=elm,
                                                   lat=lat,  # 42.0 ...
                                                   lon=lon)  # 2.7 ...

                    # draw the node in the scene
                    self.add_to_scene(graphic_object=graphic_obj)

                    nodSiz = line_container.number_of_nodes()

                    graphic_obj.index = nodSiz

                    if nodSiz > 1:
                        i1 = nodSiz - 1
                        i2 = nodSiz - 2
                        # Assuming Connector takes (scene, node1, node2) as arguments
                        segment_graphic_object = Segment(first=line_container.nodes_list[i1],
                                                         second=line_container.nodes_list[i2])

                        # register the segment in the line
                        line_container.add_segment(segment=segment_graphic_object)

                        # draw the segment in the scene
                        self.add_to_scene(graphic_object=segment_graphic_object)

        return line_container

    def update_connectors(self):
        """

        :return:
        """
        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:

            dev_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)

            for idtag, graphic_object in dev_dict.items():
                graphic_object.update_connectors()

    def create_substation(self,
                          api_object: Substation,
                          lat: float, lon: float,
                          r: float) -> SubstationGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :param r:
        :return:
        """
        graphic_object = SubstationGraphicItem(editor=self,
                                               api_object=api_object,
                                               lat=lat, lon=lon,
                                               r=r)
        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def create_voltage_level(self,
                             substation_graphics: SubstationGraphicItem,
                             api_object: VoltageLevel,
                             lat: float, lon: float,
                             r: float) -> VoltageLevelGraphicItem:
        """

        :param substation_graphics:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        :return:
        """
        graphic_object = VoltageLevelGraphicItem(parent=substation_graphics,
                                                 editor=self,
                                                 api_object=api_object,
                                                 lat=lat, lon=lon,
                                                 r=r)
        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        # self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def draw(self) -> None:
        """
        Draw the stored diagram
        """
        self.draw_diagram(diagram=self.diagram)

    def draw_diagram(self, diagram: MapDiagram) -> None:
        """
        Draw any diagram
        :param diagram: MapDiagram
        :return:
        """
        # first pass: create substations
        for category, points_group in diagram.data.items():

            if category == DeviceType.SubstationDevice.value:
                for idtag, location in points_group.locations.items():
                    self.create_substation(api_object=location.api_object,
                                           lon=location.longitude,
                                           lat=location.latitude,
                                           r=0.1)

        # second pass: create voltage levels
        for category, points_group in diagram.data.items():

            if category == DeviceType.VoltageLevelDevice.value:
                for idtag, location in points_group.locations.items():
                    if location.api_object.substation:
                        objectSubs = location.api_object.substation

                        # get the substation graphic object
                        substation_graphics = self.graphics_manager.query(elm=objectSubs)

                        # draw the voltage level
                        self.create_voltage_level(substation_graphics=substation_graphics,
                                                  api_object=location.api_object,
                                                  lon=objectSubs.longitude,
                                                  lat=objectSubs.latitude,
                                                  r=0.01)

            elif category == DeviceType.LineDevice.value:
                for idtag, location in points_group.locations.items():
                    line: Line = location.api_object
                    self.create_line(api_object=line, diagram=diagram)  # no need to add to the scene

            elif category == DeviceType.DCLineDevice.value:
                pass  # TODO: implementar

            elif category == DeviceType.HVDCLineDevice.value:
                pass  # TODO: implementar

            elif category == DeviceType.FluidNodeDevice.value:
                pass  # TODO: implementar

            elif category == DeviceType.FluidPathDevice.value:
                pass  # TODO: implementar

        # sort voltage levels at the substations
        dev_dict = self.graphics_manager.get_device_type_dict(device_type=DeviceType.SubstationDevice)
        for idtag, graphic_object in dev_dict.items():
            graphic_object.sort_voltage_levels()

    def change_size_and_pen_width_all(self, new_radius, pen_width):
        """
        Change the size and pen width of all elements in Schema.
        :param new_radius: New radius for the nodes.
        :param pen_width: New pen width for the nodes.
        """
        dev_dict = self.graphics_manager.get_device_type_dict(device_type=DeviceType.LineLocation)

        for idtag, graphic_object in dev_dict.items():
            graphic_object.resize(new_radius)
            graphic_object.change_pen_width(pen_width)

    def colour_results(self,
                       buses: List[Bus],
                       branches: List[BRANCH_TYPES],
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
        if len(branches):
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
            Sfnorm = Sfabs / np.max(Sfabs + 1e-9)

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


def generate_map_diagram(substations: List[Substation],
                         voltage_levels: List[VoltageLevel],
                         lines: List[Line],
                         dc_lines: List[DcLine],
                         hvdc_lines: List[HvdcLine],
                         fluid_nodes: List[FluidNode],
                         fluid_paths: List[FluidPath],
                         prog_func: Union[Callable, None] = None,
                         text_func: Union[Callable, None] = None,
                         name='Map diagram') -> MapDiagram:
    """
    Add a elements to the schematic scene
    :param substations: list of Substation objects
    :param voltage_levels: list of VoltageLevel objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param hvdc_lines: list of HvdcLine objects
    :param fluid_nodes: list of FluidNode objects
    :param fluid_paths: list of FluidPath objects
    :param prog_func: progress report function
    :param text_func: Text report function
    :param name: name of the diagram
    """

    diagram = MapDiagram(name=name)

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(substations)
    for i, substation in enumerate(substations):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=substation, location=MapLocation(latitude=substation.latitude,
                                                                  longitude=substation.longitude,
                                                                  api_object=substation))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(voltage_levels)
    for i, voltageLevel in enumerate(voltage_levels):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=voltageLevel, location=MapLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid nodes devices')

    nn = len(fluid_nodes)
    for i, elm in enumerate(fluid_nodes):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_upfc(branch)
        diagram.set_point(device=elm, location=MapLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(lines)
    for i, branch in enumerate(lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_line(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(dc_lines)
    for i, branch in enumerate(dc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_dc_line(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic HVDC devices')

    nn = len(hvdc_lines)
    for i, branch in enumerate(hvdc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_hvdc(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid paths devices')

    nn = len(fluid_paths)
    for i, elm in enumerate(fluid_paths):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_upfc(branch)
        diagram.set_point(device=elm, location=MapLocation())

        # register all the line locations
        for loc in elm.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    return diagram
