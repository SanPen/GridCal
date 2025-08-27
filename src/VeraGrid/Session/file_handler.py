# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
from typing import Union, List, Dict
from PySide6.QtCore import QThread, Signal

from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.veragrid.zip_interface import get_session_tree, load_session_driver_objects
from VeraGridEngine.IO.file_handler import FileOpen, FileSave, FileSavingOptions, FileOpenOptions
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.data_logger import DataLogger


class FileOpenThread(QThread):
    """
    FileOpenThread
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self,
                 file_name: Union[str, List[str]],
                 previous_circuit: Union[MultiCircuit, None] = None,
                 options: FileOpenOptions = None):
        """
        Constructor
        :param file_name: file name (s)
        :param previous_circuit: we could provide an additional circuit.
                                This is relevant if loading grid incrementals that rely on existing data
        """
        QThread.__init__(self)

        self.file_name: Union[str, List[str]] = file_name

        self.valid = False

        self.logger = Logger()

        self.circuit: Union[MultiCircuit, None] = None

        self.options = options if options is not None else FileOpenOptions()

        self.cgmes_circuit: Union[CgmesCircuit, None] = None

        self.cgmes_logger: DataLogger = DataLogger()

        self.json_files = dict()

        self._previous_circuit = previous_circuit

        self.__cancel__ = False

    def get_session_tree(self) -> Dict[str, Union[SimulationSession]]:
        """
        Get the session tree structure from a VeraGrid file
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

        file_handler = FileOpen(file_name=self.file_name,
                                previous_circuit=self._previous_circuit,
                                options=self.options)

        if self.options.crash_on_errors:
            self.circuit = file_handler.open(text_func=self.progress_text.emit,
                                             progress_func=self.progress_signal.emit)
        else:
            try:
                self.circuit = file_handler.open(text_func=self.progress_text.emit,
                                                 progress_func=self.progress_signal.emit)
            except ValueError as e:
                self.valid = False
                self.logger.add_error(msg=str(e))
                self.progress_text.emit('Error loading')
                self.done_signal.emit()
                return

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
        Get the session tree structure from a VeraGrid file
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
