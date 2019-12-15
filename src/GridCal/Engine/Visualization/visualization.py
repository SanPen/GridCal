import os
import numpy as np
import folium
from folium.plugins import MarkerCluster
from PySide2 import QtCore, QtGui, QtWidgets
from matplotlib.colors import LinearSegmentedColormap

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.file_system import get_create_gridcal_folder


def get_voltage_color_map():
    vmax = 1.2
    seq = [(0 / vmax, 'black'),
           (0.8 / vmax, 'blue'),
           (1.0 / vmax, 'green'),
           (1.05 / vmax, 'orange'),
           (1.2 / vmax, 'red')]
    voltage_cmap = LinearSegmentedColormap.from_list('vcolors', seq)

    return voltage_cmap


def get_loading_color_map():
    load_max = 1.5
    seq = [(0.0 / load_max, 'gray'),
           (0.8 / load_max, 'green'),
           (1.2 / load_max, 'orange'),
           (1.5 / load_max, 'red')]
    loading_cmap = LinearSegmentedColormap.from_list('lcolors', seq)

    return loading_cmap


def colour_the_schematic(circuit: MultiCircuit, s_bus, s_branch, voltages, loadings, types=None, losses=None,
                         failed_br_idx=None, loading_label='loading', file_name=None):
    """
    Color the grid based on the results passed
    :param circuit:
    :param s_bus:  Buses power
    :param s_branch: Branches power
    :param voltages: Buses voltage
    :param loadings: Branches load
    :param types: Buses type
    :param losses: Branches losses
    :param failed_br_idx: failed branches
    :param loading_label:
    :return:
    """

    # color nodes
    vmin = 0
    vmax = 1.2
    vrng = vmax - vmin
    vabs = np.abs(voltages)
    vang = np.angle(voltages, deg=True)
    vnorm = (vabs - vmin) / vrng
    Sbase = circuit.Sbase

    voltage_cmap = get_voltage_color_map()
    loading_cmap = get_loading_color_map()

    '''
    class BusMode(Enum):
    PQ = 1,
    PV = 2,
    REF = 3,
    NONE = 4,
    STO_DISPATCH = 5
    '''
    bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage']

    for i, bus in enumerate(circuit.buses):
        if bus.active:
            r, g, b, a = voltage_cmap(vnorm[i])
            bus.graphic_obj.set_tile_color(QtGui.QColor(r * 255, g * 255, b * 255, a * 255))

            tooltip = str(i) + ': ' + bus.name + '\n' \
                      + 'V:' + "{:10.4f}".format(vabs[i]) + " <{:10.4f}".format(vang[i]) + 'º [p.u.]\n' \
                      + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [kV]'
            if s_bus is not None:
                tooltip += '\nS: ' + "{:10.4f}".format(s_bus[i] * Sbase) + ' [MVA]'
            if types is not None:
                tooltip += '\nType: ' + bus_types[types[i]]
            bus.graphic_obj.setToolTip(tooltip)

        else:
            bus.graphic_obj.set_tile_color(QtCore.Qt.gray)

    # color branches
    if s_branch is not None:
        lnorm = abs(loadings)
        lnorm[lnorm == np.inf] = 0

        for i, branch in enumerate(circuit.branches):

            w = branch.graphic_obj.pen_width
            if branch.active:
                style = QtCore.Qt.SolidLine
                r, g, b, a = loading_cmap(lnorm[i])
                color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
            else:
                style = QtCore.Qt.DashLine
                color = QtCore.Qt.gray

            tooltip = str(i) + ': ' + branch.name
            tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
            if s_branch is not None:
                tooltip += '\nPower: ' + "{:10.4f}".format(s_branch[i]) + ' [MVA]'
            if losses is not None:
                tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'
            branch.graphic_obj.setToolTipText(tooltip)
            branch.graphic_obj.set_pen(QtGui.QPen(color, w, style))

    if failed_br_idx is not None:
        for i in failed_br_idx:
            w = circuit.branches[i].graphic_obj.pen_width
            style = QtCore.Qt.DashLine
            color = QtCore.Qt.gray
            circuit.branches[i].graphic_obj.set_pen(QtGui.QPen(color, w, style))


def get_base_map(location, zoom_start=5):
    """
    Get map with all the base defined layers
    :param location: (lat, lon)
    :param zoom_start: integer
    :return: map, marker_layer
    """

    my_map = folium.Map(location=location, zoom_start=zoom_start)

    # add possible tiles
    folium.TileLayer('cartodbpositron').add_to(my_map)
    folium.TileLayer('cartodbdark_matter').add_to(my_map)
    folium.TileLayer('openstreetmap').add_to(my_map)
    folium.TileLayer('Mapbox Bright').add_to(my_map)
    folium.TileLayer('stamentoner').add_to(my_map)

    # add markers layer
    marker_cluster = MarkerCluster().add_to(my_map)

    # add the layer control
    folium.LayerControl().add_to(my_map)

    return my_map, marker_cluster


def plot_html_map(circuit: MultiCircuit, s_bus, s_branch, voltages, loadings, types, losses=None, failed_br_idx=None,
                  loading_label='loading', file_name='map.html'):
    """
    Color the grid based on the results passed
    :param circuit:
    :param s_bus:  Buses power
    :param s_branch: Branches power
    :param voltages: Buses voltage
    :param loadings: Branches load
    :param types: Buses type
    :param losses: Branches losses
    :param failed_br_idx: failed branches
    :param loading_label:
    :return:
    """

    voltage_cmap = get_voltage_color_map()
    loading_cmap = get_loading_color_map()
    bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage']

    vmin = 0
    vmax = 1.2
    vrng = vmax - vmin
    vabs = np.abs(voltages)
    vang = np.angle(voltages, deg=True)
    vnorm = (vabs - vmin) / vrng
    Sbase = circuit.Sbase

    n = len(circuit.buses)
    longitudes = np.zeros(n)
    latitudes = np.zeros(n)
    nodes_dict = dict()
    for i, bus in enumerate(circuit.buses):
        longitudes[i] = bus.longitude
        latitudes[i] = bus.latitude
        nodes_dict[bus.name] = (bus.latitude, bus.longitude)

    # create map at he average location
    my_map, marker_cluster = get_base_map(location=circuit.get_center_location(), zoom_start=5)

    # add node positions
    for i, bus in enumerate(circuit.buses):

        tooltip = str(i) + ': ' + bus.name + '\n' \
                  + 'V:' + "{:10.4f}".format(vabs[i]) + " <{:10.4f}".format(vang[i]) + 'º [p.u.]\n' \
                  + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [kV]'
        if s_bus is not None:
            tooltip += '\nS: ' + "{:10.4f}".format(s_bus[i] * Sbase) + ' [MVA]'
        if types is not None:
            tooltip += '\nType: ' + bus_types[types[i]]

        # get the line colour
        r, g, b, a = voltage_cmap(vnorm[i])
        color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
        html_color = color.name()

        position = bus.get_coordinates()
        html = '<i>' + tooltip + '</i>'
        folium.Circle(position,
                      popup=html,
                      radius=50,
                      color=html_color,
                      tooltip=tooltip).add_to(marker_cluster)

    # add lines
    lnorm = np.abs(loadings)
    lnorm[lnorm == np.inf] = 0

    for i, branch in enumerate(circuit.branches):

        points = branch.get_coordinates()

        if not has_null_coordinates(points):
            # compose the tooltip
            tooltip = str(i) + ': ' + branch.name
            tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
            if s_branch is not None:
                tooltip += '\nPower: ' + "{:10.4f}".format(s_branch[i]) + ' [MVA]'
            if losses is not None:
                tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'

            # get the line colour
            r, g, b, a = loading_cmap(lnorm[i])
            color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
            html_color = color.name()
            weight = 3

            # draw the line
            folium.PolyLine(points,
                            color=html_color,
                            weight=weight,
                            opacity=1,
                            tooltip=tooltip).add_to(marker_cluster)

    # save the map
    my_map.save(file_name)

    print('Map saved to:\n' + file_name)


def has_null_coordinates(coord):
    """

    """
    for x, y in coord:
        if x == 0.0 and y == 0.0:
            return True
    return False