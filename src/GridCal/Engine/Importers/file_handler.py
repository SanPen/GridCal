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
import json
from warnings import warn

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Importers.json_parser import save_json_file
from GridCal.Engine.Importers.cim_parser import CIMExport
from GridCal.Engine.Importers.excel_interface import save_excel, load_from_xls, interpret_excel_v3, interprete_excel_v2
from GridCal.Engine.Importers.matpower_parser import interpret_data_v1
from GridCal.Engine.Importers.dgs_parser import dgs_to_circuit
from GridCal.Engine.Importers.matpower_parser import parse_matpower_file
from GridCal.Engine.Importers.dpx_parser import load_dpx
from GridCal.Engine.Importers.ipa_parser import load_iPA
from GridCal.Engine.Importers.json_parser import parse_json
from GridCal.Engine.Importers.psse_parser import PSSeParser
from GridCal.Engine.Importers.cim_parser import CIMImport


from PyQt5.QtCore import QThread, pyqtSignal


class FileOpen:

    def __init__(self, file_name):
        """
        File open handler
        :param file_name: name of the file
        """
        self.file_name = file_name

        self.circuit = MultiCircuit()

        self.logger = list()

    def open(self):
        """
        Load GridCal compatible file
        @return: logger with information
        """
        logger = list()

        if os.path.exists(self.file_name):
            name, file_extension = os.path.splitext(self.file_name)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                data_dictionary = load_from_xls(self.file_name)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in data_dictionary.keys():

                    interpret_data_v1(self.circuit, data_dictionary)
                    # return self.circuit
                elif data_dictionary['version'] == 2.0:
                    interprete_excel_v2(self.circuit, data_dictionary)
                    # return self.circuit
                elif data_dictionary['version'] == 3.0:
                    interpret_excel_v3(self.circuit, data_dictionary)
                    # return self.circuit
                else:
                    warn('The file could not be processed')
                    # return self.circuit

            elif file_extension.lower() == '.dgs':
                circ = dgs_to_circuit(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.m':
                circ = parse_matpower_file(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.dpx':
                circ, logger = load_dpx(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.json':

                # the json file can be the GridCAl one or the iPA one...
                data = json.load(open(self.file_name))

                if type(data) == dict():
                    if 'Red' in data.keys():
                        circ = load_iPA(self.file_name)
                        self.circuit.buses = circ.buses
                        self.circuit.branches = circ.branches
                        self.circuit.assign_circuit(circ)
                    else:
                        logger.append('Unknown json format')

                elif type(data) == list():
                    circ = parse_json(self.file_name)
                    self.circuit.buses = circ.buses
                    self.circuit.branches = circ.branches
                    self.circuit.assign_circuit(circ)
                else:
                    logger.append('Unknown json format')

            elif file_extension.lower() == '.raw':
                parser = PSSeParser(self.file_name)
                circ = parser.circuit
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)
                logger = parser.logger

            elif file_extension.lower() == '.xml':
                parser = CIMImport()
                circ = parser.load_cim_file(self.file_name)
                self.circuit.assign_circuit(circ)
                logger = parser.logger

        else:
            warn('The file does not exist.')
            logger.append(self.file_name + ' does not exist.')

        self.logger = logger

        return self.circuit


class FileSave:

    def __init__(self, circuit: MultiCircuit, file_name):
        """
        File saver
        :param circuit: MultiCircuit
        :param file_name: file name to save to
        """
        self.circuit = circuit

        self.file_name = file_name

    def save(self):
        """
        Save the file in the corresponding format
        :return: logger with information
        """
        if self.file_name.endswith('.xlsx'):
            logger = self.save_excel()

        elif self.file_name.endswith('.json'):
            logger = self.save_json()

        elif self.file_name.endswith('.xml'):
            logger = self.save_cim()

        else:
            logger = list()
            logger.append('File path extension not understood\n' + self.file_name)

        return logger

    def save_excel(self):
        """
        Save the circuit information in excel format
        :return: logger with information
        """

        logger = save_excel(self.circuit, self.file_name)

        return logger

    def save_json(self):
        """
        Save the circuit information in json format
        :return:logger with information
        """

        logger = save_json_file(self.file_name, self.circuit)
        return logger

    def save_cim(self):
        """
        Save the circuit information in CIM format
        :return: logger with information
        """

        cim = CIMExport(self.circuit)
        cim.save(file_name=self.file_name)

        return cim.logger


class FileOpenThread(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, app, file_name):
        """

        :param app: instance of MainGui
        """
        QThread.__init__(self)

        self.app = app

        self.file_name = file_name

        self.valid = False

        self.logger = list()

        self.circuit = None

        self.__cancel__ = False

    def progress_callback(self, val):
        """
        Send progress report
        :param val: lambda value
        :return: None
        """
        self.progress_text.emit('Running voltage collapse lambda:' + "{0:.2f}".format(val) + '...')

    def open_file_process(self, filename):
        """
        process to open a file without asking
        :return:
        """

        # print(filename)
        self.circuit = MultiCircuit()

        path, fname = os.path.split(filename)

        self.progress_text.emit('Loading ' + fname + '...')

        self.logger = list()

        file_handler = FileOpen(file_name=filename)
        self.circuit = file_handler.open()
        self.logger += file_handler.logger
        self.valid = True

        # try:
        #     self.logger += self.circuit.load_file(filename=filename)
        #
        #     self.valid = True
        #
        # except Exception as ex:
        #     exc_type, exc_value, exc_traceback = sys.exc_info()
        #     self.logger.append(str(exc_traceback) + '\n' + str(exc_value))
        #     self.valid = False

        # post events
        self.progress_text.emit('Creating schematic...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.open_file_process(filename=self.file_name)

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True

