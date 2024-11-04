# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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
