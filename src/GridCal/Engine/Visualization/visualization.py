import os
import numpy as np
import folium
from folium.plugins import MarkerCluster
from PySide2 import QtCore, QtGui, QtWidgets
from matplotlib.colors import LinearSegmentedColormap

import matplotlib.pyplot as plt
import matplotlib.cm as mplcm
import matplotlib.colors as colors

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.file_system import get_create_gridcal_folder
from GridCal.Engine.Devices.editable_device import DeviceType


def get_voltage_color_map():
    """
    Voltage Color map
    :return: colormap
    """
    vmax = 1.2
    seq = [(0 / vmax, 'black'),
           (0.8 / vmax, 'blue'),
           (1.0 / vmax, 'green'),
           (1.05 / vmax, 'orange'),
           (1.2 / vmax, 'red')]
    voltage_cmap = LinearSegmentedColormap.from_list('vcolors', seq)

    return voltage_cmap


def get_loading_color_map():
    """
    Loading Color map
    :return: colormap
    """
    load_max = 1.5
    seq = [(0.0 / load_max, 'gray'),
           (0.8 / load_max, 'green'),
           (1.2 / load_max, 'orange'),
           (1.5 / load_max, 'red')]
    loading_cmap = LinearSegmentedColormap.from_list('lcolors', seq)

    return loading_cmap


def colour_sub_schematic(Sbase,
                         buses,
                         branches,
                         hvdc_lines,
                         Sbus,
                         Sf,
                         St,
                         voltages,
                         loadings,
                         types=None,
                         losses=None,
                         hvdc_sending_power=None,
                         hvdc_losses=None,
                         hvdc_loading=None,
                         failed_br_idx=None,
                         loading_label='loading',
                         ma=None,
                         theta=None,
                         Beq=None,
                         use_flow_based_width=False,
                         min_branch_width=5,
                         max_branch_width=5,
                         min_bus_width=20,
                         max_bus_width=20):
    """
    Color objects based on the results passed
    :param Sbase:
    :param buses: list of matching bus objects
    :param branches: list of branches without HVDC
    :param hvdc_lines: list of HVDC lines
    :param Sbus:  Buses power
    :param Sf: Branches power from the "from" bus
    :param St: Branches power from the "to" bus
    :param voltages: Buses voltage
    :param loadings: Branches load
    :param types: Buses type
    :param losses: Branches losses
    :param hvdc_sending_power:
    :param hvdc_losses:
    :param hvdc_loading:
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

    if Sbus is not None:
        Pabs = np.abs(Sbus)
        Pnorm = Pabs / Pabs.max()
    else:
        Pnorm = np.zeros(len(buses))

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
    max_flow = 1

    for i, bus in enumerate(buses):
        if bus.graphic_obj is not None:
            if bus.active:
                r, g, b, a = voltage_cmap(vnorm[i])
                bus.graphic_obj.set_tile_color(QtGui.QColor(r * 255, g * 255, b * 255, a * 255))

                tooltip = str(i) + ': ' + bus.name
                if types is not None:
                    tooltip += ': ' + bus_types[types[i]]
                tooltip += '\n'

                tooltip += "%-10s %10.4f < %10.4fº [p.u.]\n" % ("V", vabs[i], vang[i])
                tooltip += "%-10s %10.4f < %10.4fº [kV]\n" % ("V", vabs[i], vang[i])

                if Sbus is not None:
                    tooltip += "%-10s %10.4f [MW]\n" % ("P", Sbus[i].real)
                    tooltip += "%-10s %10.4f [MVAr]\n" % ("Q", Sbus[i].imag)

                bus.graphic_obj.setToolTip(tooltip)

                if use_flow_based_width:
                    h = int(np.floor(min_bus_width + Pnorm[i] * (max_bus_width - min_bus_width)))
                    bus.graphic_obj.change_size(bus.graphic_obj.w, h)

            else:
                bus.graphic_obj.set_tile_color(QtCore.Qt.gray)

    # color branches
    if Sf is not None:

        lnorm = np.abs(loadings)
        lnorm[lnorm == np.inf] = 0
        Sfabs = np.abs(Sf)
        max_flow = Sfabs.max()

        if hvdc_sending_power is not None:
            if len(hvdc_sending_power) > 0:
                max_flow = max(max_flow, np.abs(hvdc_sending_power).max())

        Sfnorm = Sfabs / max_flow

        for i, branch in enumerate(branches):
            if branch.graphic_obj is not None:

                if use_flow_based_width:
                    w = int(np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                else:
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

                branch.graphic_obj.setToolTipText(tooltip)
                branch.graphic_obj.set_colour(color, w, style)

    if failed_br_idx is not None:
        for i in failed_br_idx:
            if branches[i].graphic_obj is not None:
                w = branches[i].graphic_obj.pen_width
                style = QtCore.Qt.DashLine
                color = QtCore.Qt.gray
                branches[i].graphic_obj.set_pen(QtGui.QPen(color, w, style))

    if hvdc_sending_power is not None:

        hvdc_sending_power_norm = np.abs(hvdc_sending_power) / max_flow

        for i, elm in enumerate(hvdc_lines):

            if elm.graphic_obj is not None:

                if use_flow_based_width:
                    w = int(np.floor(min_branch_width + hvdc_sending_power_norm[i] * (max_branch_width - min_branch_width)))
                else:
                    w = elm.graphic_obj.pen_width

                if elm.active:
                    style = QtCore.Qt.SolidLine
                    r, g, b, a = loading_cmap(abs(hvdc_loading[i]))
                    color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                else:
                    style = QtCore.Qt.DashLine
                    color = QtCore.Qt.gray

                tooltip = str(i) + ': ' + elm.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(abs(hvdc_loading[i]) * 100) + ' [%]'

                tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_sending_power[i]) + ' [MW]'

                if hvdc_losses is not None:
                    tooltip += '\nPower (to):\t' + "{:10.4f}".format(-hvdc_sending_power[i] + hvdc_losses[i]) + ' [MW]'
                    tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'

                elm.graphic_obj.setToolTipText(tooltip)
                elm.graphic_obj.set_colour(color, w, style)


def colour_the_schematic(circuit: MultiCircuit, Sbus, Sf, voltages, loadings,
                         types=None, losses=None, St=None,
                         hvdc_sending_power=None, hvdc_losses=None, hvdc_loading=None,
                         failed_br_idx=None, loading_label='loading',
                         ma=None,
                         theta=None,
                         Beq=None,
                         use_flow_based_width=False,
                         min_branch_width=1,
                         max_branch_width=1,
                         min_bus_width=20,
                         max_bus_width=20,
                         file_name=None):
    """
    Color the grid based on the results passed
    :param circuit:
    :param Sbus:  Buses power
    :param Sf: Branches power seen from the "from" bus
    :param voltages: Buses voltage
    :param loadings: Branches load
    :param types: Buses type
    :param losses: Branches losses
    :param St: power seen from the "to" bus
    :param hvdc_sending_power:
    :param hvdc_losses:
    :param hvdc_loading:
    :param failed_br_idx: failed branches
    :param loading_label:
    :param ma
    :param theta
    :param Beq
    :param file_name: Completely ignore this. It exist for interface compatibility
    :return:
    """

    colour_sub_schematic(Sbase=circuit.Sbase,
                         buses=circuit.buses,
                         branches=circuit.get_branches_wo_hvdc(),
                         hvdc_lines=circuit.hvdc_lines,
                         Sbus=Sbus,
                         Sf=Sf,
                         St=St if St is not None else Sf,
                         voltages=voltages,
                         loadings=loadings,
                         types=types,
                         losses=losses,
                         hvdc_sending_power=hvdc_sending_power,
                         hvdc_losses=hvdc_losses,
                         hvdc_loading=hvdc_loading,
                         failed_br_idx=failed_br_idx,
                         loading_label=loading_label,
                         ma=ma,
                         theta=theta,
                         Beq=Beq,
                         use_flow_based_width=use_flow_based_width,
                         min_branch_width=min_branch_width,
                         max_branch_width=max_branch_width,
                         min_bus_width=min_bus_width,
                         max_bus_width=max_bus_width,
                         )


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


def plot_html_map(circuit: MultiCircuit, Sbus, Sf, voltages, loadings, types, losses=None,
                  St=None,
                  failed_br_idx=None,
                  loading_label='loading',
                  use_flow_based_width=False,
                  min_branch_width=5,
                  max_branch_width=5,
                  min_bus_width=20,
                  max_bus_width=20,
                  file_name='map.html'):
    """
    Color the grid based on the results passed
    :param circuit:
    :param Sbus:  Buses power
    :param Sf: Branches power
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
        if Sbus is not None:
            tooltip += '\nS: ' + "{:10.4f}".format(Sbus[i] * Sbase) + ' [MVA]'
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
    branches = circuit.get_branches()
    for i, branch in enumerate(branches):

        points = branch.get_coordinates()

        if not has_null_coordinates(points):
            # compose the tooltip
            tooltip = str(i) + ': ' + branch.name
            tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
            if Sf is not None:
                tooltip += '\nPower: ' + "{:10.4f}".format(Sf[i]) + ' [MVA]'
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


def convert_to_hex(rgba_color):
    """
    Convert an RGBa reference to HEX
    :param rgba_color: RGBa color
    :return: HEX color
    """
    red = int(rgba_color.red * 255)
    green = int(rgba_color.green * 255)
    blue = int(rgba_color.blue * 255)
    return '0x{r:02x}{g:02x}{b:02x}'.format(r=red, g=green, b=blue)


def get_n_colours(n, colormap='gist_rainbow'):
    """
    get a number of different colours
    :param n: number of different colours
    :param colormap: colormap name to use
    :return: list of colours in RGBa
    """
    cm = plt.get_cmap(colormap)
    cNorm = colors.Normalize(vmin=0, vmax=n - 1)
    scalarMap = mplcm.ScalarMappable(norm=cNorm, cmap=cm)

    # alternative:
    # [cm(1. * i / NUM_COLORS) for i in range(NUM_COLORS)]

    return [scalarMap.to_rgba(i) for i in range(n)]
