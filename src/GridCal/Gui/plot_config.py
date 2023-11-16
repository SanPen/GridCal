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

import PySide6  # this line is necessary so that Matplotlib recognises that PySide is the Qt Backend
import matplotlib
matplotlib.use('Qt6Agg')
from matplotlib import pyplot as plt  # leave here


########################################################################################################################
# Set Matplotlib global parameters
########################################################################################################################
# if 'fivethirtyeight' in plt.style.available:
#     plt.style.use('fivethirtyeight')

SMALL_SIZE = 8
MEDIUM_SIZE = 10
BIGGER_SIZE = 12
LINEWIDTH = 1

LEFT = 0.12
RIGHT = 0.98
TOP = 0.8
BOTTOM = 0.2
matplotlib.rc('font', size=SMALL_SIZE)  # controls default text sizes
matplotlib.rc('axes', titlesize=SMALL_SIZE)  # font size of the axes title
matplotlib.rc('axes', labelsize=SMALL_SIZE)  # font size of the x and y labels
matplotlib.rc('xtick', labelsize=SMALL_SIZE)  # font size of the tick labels
matplotlib.rc('ytick', labelsize=SMALL_SIZE)  # font size of the tick labels
matplotlib.rc('legend', fontsize=SMALL_SIZE)  # legend font size
matplotlib.rc('figure', titlesize=MEDIUM_SIZE)  # font size of the figure title
