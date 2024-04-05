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
import os
from typing import Union, List, Dict
from PySide6.QtCore import QThread, Signal

from GridCal.Session.session import SimulationSession
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.zip_interface import get_session_tree, load_session_driver_objects
from GridCalEngine.IO.file_handler import FileOpen, FileSave, FileSavingOptions
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.data_logger import DataLogger


class FileOpenThread(QThread):
    """
    FileOpenThread
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, file_name: Union[str, List[str]]):
        """
        Constructor
        :param file_name: file name (s)
        """
        QThread.__init__(self)

        self.file_name: Union[str, List[str]] = file_name

        self.valid = False

        self.logger = Logger()

        self.circuit: Union[MultiCircuit, None] = None

        self.cgmes_circuit: Union[CgmesCircuit, None] = None

        self.cgmes_logger: DataLogger = DataLogger()

        self.json_files = dict()

        self.__cancel__ = False

    def get_session_tree(self) -> Dict[str, Union[SimulationSession]]:
        """
        Get the session tree structure from a GridCal file
        :return:
        """
        if isinstance(self.file_name, str):
            if self.file_name.endswith('.gridcal'):
                return get_session_tree(self.file_name)
            else:
                return dict()
        else:
            return dict()

    def load_session_objects(self, session_name: str, study_name: str):
        """
        Load the numpy objects of the session
        :param session_name: Name of the session (i.e. GUI Session)
        :param study_name: Name of the study i.e Power Flow)
        :return: Dictionary (name: array)
        """
        if isinstance(self.file_name, str):
            if self.file_name.endswith('.gridcal'):
                return load_session_driver_objects(file_name_zip=self.file_name,
                                                   session_name=session_name,
                                                   study_name=study_name)
            else:
                return dict()
        else:
            return dict()

    def run(self) -> None:
        """
        run the file open procedure
        """
        self.circuit = MultiCircuit()

        if isinstance(self.file_name, list):
            path, fname = os.path.split(self.file_name[0])
            self.progress_text.emit('Loading ' + fname + '...')
        else:
            path, fname = os.path.split(self.file_name)
            self.progress_text.emit('Loading ' + fname + '...')

        self.logger = Logger()

        file_handler = FileOpen(file_name=self.file_name)

        self.circuit = file_handler.open(text_func=self.progress_text.emit,
                                         progress_func=self.progress_signal.emit)

        self.json_files = file_handler.json_files

        self.cgmes_circuit = file_handler.cgmes_circuit
        self.cgmes_logger = file_handler.cgmes_logger

        self.logger += file_handler.logger
        self.valid = True

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self) -> None:
        """
        Set the cancel flag
        """
        self.__cancel__ = True


class FileSaveThread(QThread):
    """
    Thread to save
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self,
                 circuit: MultiCircuit,
                 file_name: str,
                 options: FileSavingOptions):
        """
        Constructor
        :param circuit: MultiCircuit instance
        :param file_name: name of the file where to save
        :param options: FileSavingOptions
        """
        QThread.__init__(self)

        self.circuit = circuit

        self.file_name = file_name

        self.valid = False

        self.options = options

        self.logger = Logger()

        self.error_msg = ''

        self.__cancel__ = False

    def get_session_tree(self) -> Dict:
        """
        Get the session tree structure from a GridCal file
        :return:
        """
        if isinstance(self.file_name, str):
            if self.file_name.endswith('.gridcal'):
                return get_session_tree(self.file_name)
            else:
                return dict()
        else:
            return dict()

    def load_session_objects(self, session_name: str, study_name: str):
        """
        Load the numpy objects of the session
        :param session_name: Name of the session (i.e. GUI Session)
        :param study_name: Name of the study i.e Power Flow)
        :return: Dictionary (name: array)
        """
        if isinstance(self.file_name, str):
            if self.file_name.endswith('.gridcal'):
                return load_session_driver_objects(self.file_name, session_name, study_name)
            else:
                return dict()
        else:
            return dict()

    def run(self) -> None:
        """
        run the file save procedure
        @return:
        """

        path, fname = os.path.split(self.file_name)

        self.progress_text.emit('Flushing ' + fname + ' into ' + fname + '...')

        self.logger = Logger()

        file_handler = FileSave(circuit=self.circuit,
                                file_name=self.file_name,
                                options=self.options,
                                text_func=self.progress_text.emit,
                                progress_func=self.progress_signal.emit)
        try:
            self.logger = file_handler.save()
        except PermissionError:
            self.logger.add_error("File permission denied. Do you have the file open? Do you have write permissions?")

        self.valid = True

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self):
        """
        Activate the cancel flag
        """
        self.__cancel__ = True
