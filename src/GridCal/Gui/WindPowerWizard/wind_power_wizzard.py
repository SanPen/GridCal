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

import numpy as np
from typing import List

from PySide6 import QtCore, QtWidgets
from GridCal.Gui.SolarPowerWizard.solar_power_wizzard import get_pv_lib_weather_df


class WindFarmWizard(QtWidgets.QDialog):
    """
    New solar photovoltaic wizard window
    """

    def __init__(self, time_array: List[str], peak_power: float, latitude: float, longitude: float,
                 gen_name='', bus_name='',
                 title='Wind farm wizard'):
        """

        :param time_array: array of time values
        :param peak_power: generator peak power in MW
        :param latitude: latitude (float)
        :param longitude: longitude (float)
        :param title: Window title
        """
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.selected_indices: List[int] = list()

        self.label_gen = QtWidgets.QLabel()
        self.label_gen.setText("Generator {}".format(gen_name))

        self.label_bus = QtWidgets.QLabel()
        self.label_bus.setText("Bus: {}".format(bus_name))

        self.label_peak = QtWidgets.QLabel()
        self.label_peak.setText("peak power {} MW".format(peak_power))

        self.lat_label = QtWidgets.QLabel()
        self.lat_label.setText("Latitude {} deg".format(latitude))

        self.lon_label = QtWidgets.QLabel()
        self.lon_label.setText("Longitude {} deg".format(longitude))

        self.peak_power = peak_power
        self.latitude = latitude
        self.longitude = longitude
        self.time_array = time_array
        self.P = np.zeros(len(time_array))

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label_gen)
        self.main_layout.addWidget(self.label_bus)
        self.main_layout.addWidget(self.label_peak)
        self.main_layout.addWidget(self.lat_label)
        self.main_layout.addWidget(self.lon_label)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        h = 260
        self.resize(h, int(0.8 * h))

    def compute(self, wind_speed):
        pass

    def accept_click(self):
        """
        Accept and close
        """
        ok, df = get_pv_lib_weather_df(time_array=self.time_array,
                                       latitude=self.latitude,
                                       longitude=self.longitude,
                                       peak_power=self.peak_power)

        if ok:
            self.P = df['P'].values / 1e6  # Power in MW

        self.is_accepted = ok
        self.accept()
