# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Tuple
from matplotlib.colors import LinearSegmentedColormap

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as mplcm
import matplotlib.colors as colors


def get_voltage_color_map() -> matplotlib.colors.LinearSegmentedColormap:
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


def get_loading_color_map() -> matplotlib.colors.LinearSegmentedColormap:
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


def has_null_coordinates(coord: List[Tuple[float, float]]) -> bool:
    """
    are the coordinates zero?
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

