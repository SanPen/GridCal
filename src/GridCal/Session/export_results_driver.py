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

from typing import List
from PySide6.QtCore import QThread, Signal
from GridCalEngine.IO.gridcal.results_export import export_drivers
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.types import DRIVER_OBJECTS
from GridCalEngine.basic_structures import Logger


class ExportAllThread(QThread):
    """
    ExportAllThread
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, circuit: MultiCircuit, drivers_list: List[DRIVER_OBJECTS], file_name: str):
        """
        Constructor
        :param circuit: Grid circuit
        :param drivers_list: list of GridCal simulation drivers
        :param file_name: name of the file where to save (.zip)
        """
        QThread.__init__(self)

        self.circuit: MultiCircuit = circuit

        self.drivers_list: List[DRIVER_OBJECTS] = drivers_list

        self.file_name: str = file_name

        self.valid: bool = False

        self.logger = Logger()

        self.error_msg: str = ""

        self.__cancel__ = False

    def run(self) -> None:
        """
        run the file save procedure
        """

        # try:
        export_drivers(drivers_list=self.drivers_list,
                       file_name=self.file_name,
                       text_func=self.progress_text.emit,
                       progress_func=self.progress_signal.emit,
                       logger=self.logger)

        self.valid = True

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self):
        """
        Cancel progress
        """
        self.__cancel__ = True
