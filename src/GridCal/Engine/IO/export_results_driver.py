# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import os
from io import StringIO
import zipfile
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.IO.zip_interface import save_data_frames_to_zip
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices import DeviceType


class ExportAllThread(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, circuit, simulations_list, file_name):
        """
        Constructor
        :param simulations_list: list of GridCal simulation drivers
        :param file_name: name of the file where to save (.zip)
        """
        QThread.__init__(self)

        self.circuit = circuit

        self.simulations_list = simulations_list

        self.file_name = file_name

        self.valid = False

        self.logger = Logger()

        self.error_msg = ''

        self.__cancel__ = False

    def run(self):
        """
        run the file save procedure
        """

        # try:
        path, fname = os.path.split(self.file_name)

        self.progress_text.emit('Flushing ' + fname + ' into ' + fname + '...')

        self.logger = Logger()

        names_dict = {DeviceType.BusDevice: self.circuit.bus_names,
                      DeviceType.BranchDevice: self.circuit.branch_names,
                      DeviceType.BusDevice.LoadDevice: self.circuit.get_load_names(),
                      DeviceType.BusDevice.GeneratorDevice: self.circuit.get_controlled_generator_names(),
                      DeviceType.BusDevice.BatteryDevice: self.circuit.get_battery_names()}

        # open zip file for writing
        try:
            with zipfile.ZipFile(self.file_name, 'w', zipfile.ZIP_DEFLATED) as myzip:

                n = len(self.simulations_list)

                for k, driver in enumerate(self.simulations_list):

                    self.progress_signal.emit((k + 1) / n * 100.0)

                    for available_result in driver.results.available_results:

                        # ge the result type definition
                        result_name, device_type = available_result.value

                        self.progress_text.emit('flushing ' + driver.results.name + ' ' + result_name)

                        # save the DataFrame to the buffer
                        mdl = driver.results.mdl(result_type=available_result)

                        if mdl is not None:
                            with StringIO() as buffer:
                                filename = driver.results.name + ' ' + result_name + '.csv'
                                try:
                                    mdl.save_to_csv(buffer)
                                    myzip.writestr(filename, buffer.getvalue())
                                except ValueError:
                                    self.logger.add_error('Value error', filename)
                        else:
                            self.logger.add_info('No results for ' + driver.results.name + ' - ' + result_name)

        except PermissionError:
            self.logger.add('Permission error.\nDo you have the file open?')

        self.valid = True

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True