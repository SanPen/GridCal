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

import numpy as np
from typing import List, Union, Tuple
from datetime import datetime, timedelta
import pandas as pd
import requests
import pvlib
from matplotlib import pyplot as plt
from PySide6 import QtCore, QtWidgets
from GridCal.Gui.messages import error_msg
from GridCalEngine.basic_structures import DateVec
from GridCal.Gui.SolarPowerWizard.gui import Ui_MainWindow
from GridCal.Gui.GuiFunctions import PandasModel


def get_pv_lib_weather_df(time_array: DateVec, latitude, longitude, peak_power) -> Tuple[bool, pd.DataFrame]:
    """

    :param time_array:
    :param latitude:
    :param longitude:
    :param peak_power:
    :return:
    """
    max_year_span = 2015 - 2010  # 10 years, this is due to PVLIB's database

    ts1 = time_array[0]
    ts2 = time_array[-1]
    year_span = ts2.year - ts1.year

    if year_span <= max_year_span:

        s = datetime(year=2010, month=ts1.month, day=ts1.day, hour=ts1.hour, minute=ts1.minute)
        e = datetime(year=2010 + year_span, month=ts2.month, day=ts2.day, hour=ts2.hour, minute=ts2.minute)

        new_ts = pd.to_datetime([datetime(year=2010 + ts.year - ts1.year,
                                          month=ts.month,
                                          day=ts.day,
                                          hour=ts.hour,
                                          minute=ts.minute) for ts in time_array]).values.astype(float).astype(
            np.int64)

        try:

            data, meta, inputs = pvlib.iotools.get_pvgis_hourly(latitude=latitude,
                                                                longitude=longitude,
                                                                start=s,
                                                                end=e,
                                                                pvcalculation=True,
                                                                peakpower=peak_power * 1e3,  # kW
                                                                )

            data.index = data.index.values.astype(float).astype(np.int64)
            data2 = data.reindex(new_ts).interpolate(method='linear')

            P = data2['P'].values / 1e6  # Power in MW

            return True, data2

        except requests.HTTPError as err:
            error_msg("pvlib's http request failed :(\n" + str(err))
            return False, pd.DataFrame(data={'P': np.zeros(len(time_array))})

    else:
        error_msg("The time span of your profile is {} year(s), Pvlib's span is 10 years maximum")
        return False, pd.DataFrame(data={'P': np.zeros(len(time_array))})


class SolarPvWizard(QtWidgets.QDialog):
    """
    New solar photovoltaic wizard window
    """

    def __init__(self, time_array: List[str], peak_power: float, latitude: float, longitude: float,
                 gen_name='', bus_name='',
                 title='solar photovoltaic wizard'):
        """

        :param time_array: array of time values
        :param peak_power: generator peak power in MW
        :param latitude: latitude (float)
        :param longitude: longitude (float)
        :param title: Window title
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)

        self.is_accepted: bool = False
        self.selected_indices: List[int] = list()

        self.ui.label_gen.setText("Generator {}".format(gen_name))
        self.ui.label_bus.setText("Bus: {}".format(bus_name))
        self.ui.powerSpinBox.setValue(peak_power)
        self.ui.latitudeSpinBox.setValue(latitude)
        self.ui.longitudeSpinBox.setValue(longitude)

        self.time_array = time_array
        self.P = np.zeros(len(time_array))

        # accept button
        self.ui.acceptButton.clicked.connect(self.accept_click)
        self.ui.generateButton.clicked.connect(self.generate_click)
        self.ui.plotButton.clicked.connect(self.plot)

        self.setWindowTitle(title)

        h = 260
        self.resize(h, int(0.8 * h))

        self.df: Union[pd.DataFrame, None] = None
        self.ok = False

        self.update_results()

    def update_results(self):
        """

        :return:
        """
        df = pd.DataFrame(data=self.P, index=self.time_array, columns=['P (MW)'])
        mdl = PandasModel(data=df)
        self.ui.resultsTableView.setModel(mdl)

    def generate_click(self) -> None:
        """
        Accept and close
        """
        self.ok, self.df = get_pv_lib_weather_df(time_array=self.time_array,
                                                 latitude=self.ui.latitudeSpinBox.value(),
                                                 longitude=self.ui.longitudeSpinBox.value(),
                                                 peak_power=self.ui.powerSpinBox.value())
        if self.ok:
            self.P = self.df['P'].values / 1e6  # Power in MW
            self.update_results()

        else:
            self.ui.resultsTableView.setModel(None)

    def plot(self):

        df = pd.DataFrame(data=self.P, index=self.time_array, columns=['P (MW)'])
        df.plot()
        plt.show()

    def accept_click(self):
        """
        Accept and close
        """

        self.is_accepted = self.ok
        self.accept()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)

    st = datetime(year=2018, month=1, day=1)
    time_arr = pd.to_datetime([st + timedelta(hours=i) for i in range(200)])

    window = SolarPvWizard(time_array=time_arr, peak_power=20, latitude=32.2, longitude=-110.9)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
