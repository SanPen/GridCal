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
from __future__ import annotations
import os
import json

from collections.abc import Callable
from typing import Union, List, Any, Dict, TYPE_CHECKING

from GridCalEngine.IO.cim.cgmes.gridcal_to_cgmes import gridcal_to_cgmes, create_cgmes_headers
from GridCalEngine.IO.cim.cgmes.cgmes_export import CimExporter
from GridCalEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from GridCalEngine.basic_structures import Logger
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.gridcal.json_parser import save_json_file_v3
from GridCalEngine.IO.gridcal.excel_interface import save_excel, load_from_xls, interpret_excel_v3, interprete_excel_v2
from GridCalEngine.IO.gridcal.pack_unpack import gather_model_as_data_frames, parse_gridcal_data, gather_model_as_jsons
from GridCalEngine.IO.matpower.matpower_parser import interpret_data_v1, parse_matpower_file
from GridCalEngine.IO.dgs.dgs_parser import dgs_to_circuit
from GridCalEngine.IO.others.dpx_parser import load_dpx
from GridCalEngine.IO.others.ipa_parser import load_iPA
from GridCalEngine.IO.gridcal.json_parser import parse_json, parse_json_data_v2, parse_json_data_v3
from GridCalEngine.IO.raw.raw_parser_writer import read_raw, write_raw
from GridCalEngine.IO.raw.raw_to_gridcal import psse_to_gridcal
from GridCalEngine.IO.raw.gridcal_to_raw import gridcal_to_raw
from GridCalEngine.IO.epc.epc_parser import PowerWorldParser
from GridCalEngine.IO.cim.cim16.cim_parser import CIMImport, CIMExport
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit, is_valid_cgmes
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import cgmes_to_gridcal
from GridCalEngine.IO.gridcal.zip_interface import save_gridcal_data_to_zip, get_frames_from_zip
from GridCalEngine.IO.gridcal.sqlite_interface import save_data_frames_to_sqlite, open_data_frames_from_sqlite
from GridCalEngine.IO.gridcal.h5_interface import save_h5, open_h5
from GridCalEngine.IO.raw.rawx_parser_writer import parse_rawx, write_rawx
from GridCalEngine.IO.others.pypsa_parser import parse_netcdf, parse_hdf5
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.enumerations import CGMESVersions, SimulationTypes

if TYPE_CHECKING:
    from GridCalEngine.Simulations.types import DRIVER_OBJECTS


class FileSavingOptions:
    """
    This class is to store the extra stuff that needs to be passed to save more complex files
    """

    def __init__(self,
                 cgmes_boundary_set: str = "",
                 simulation_drivers: List[DRIVER_OBJECTS] = None,
                 sessions_data: List[DriverToSave] = None,
                 dictionary_of_json_files: Dict[str, Dict[str, Any]] = None,
                 cgmes_version: CGMESVersions = CGMESVersions.v2_4_15,
                 cgmes_profiles: Union[None, List[cgmesProfile]] = None,
                 one_file_per_profile: bool = False):
        """
        Constructor
        :param cgmes_boundary_set: CGMES boundary set zip file path
        :param simulation_drivers: List of Simulation Drivers
        :param sessions_data: List of sessions_data
        :param dictionary_of_json_files: Dictionary of json files
        :param cgmes_version: Version to use with CGMES
        :param cgmes_profiles: CGMES profile list to export
        :param one_file_per_profile: use one file per profile?
        """

        self.cgmes_version: CGMESVersions = cgmes_version

        self.cgmes_boundary_set: str = cgmes_boundary_set

        self.simulation_drivers: List[DRIVER_OBJECTS] = simulation_drivers if simulation_drivers else list()

        self.sessions_data: List[DriverToSave] = sessions_data if sessions_data else list()

        self.dictionary_of_json_files = dictionary_of_json_files if dictionary_of_json_files else dict()

        # File type description as it appears in the file saving dialogue i.e. GridCal zip (*.gridcal)
        self.type_selected: str = ""

        # CGMES profile list
        self.cgmes_profiles = cgmes_profiles if cgmes_profiles is not None else [cgmesProfile.EQ,
                                                                                 cgmesProfile.OP,
                                                                                 cgmesProfile.SC,
                                                                                 cgmesProfile.TP,
                                                                                 cgmesProfile.SV,
                                                                                 cgmesProfile.SSH,
                                                                                 cgmesProfile.DY,
                                                                                 cgmesProfile.DL,
                                                                                 cgmesProfile.GL]

        # use one file per profile?
        self.one_file_per_profile = one_file_per_profile

    def get_power_flow_results(self) -> Union[None, PowerFlowResults]:
        """
        Try to extract the power flow results
        :return: None or PowerFlowResults
        """
        for data in self.sessions_data:
            if data.tpe == SimulationTypes.PowerFlow_run:
                return data.results

        return None


class FileOpen:
    """
    File open interface
    """

    def __init__(self, file_name: Union[str, List[str]]):
        """
        File open handler
        :param file_name: name of the file
        """
        self.file_name: Union[str, List[str]] = file_name

        self.circuit: Union[MultiCircuit, None] = None

        self.cgmes_circuit: Union[CgmesCircuit, None] = None

        self.json_files = dict()

        self.logger = Logger()

        self.cgmes_logger = DataLogger()

        if isinstance(self.file_name, str):
            if not os.path.exists(self.file_name):
                raise Exception("File not found :( \n{}".format(self.file_name))
        elif isinstance(self.file_name, list):
            for fname in self.file_name:
                if not os.path.exists(fname):
                    raise Exception("File not found :( \n{}".format(fname))
        else:
            raise Exception("file_name type not supported :( \n{}".format(self.file_name))

    def open(self, text_func: Union[None, Callable] = None,
             progress_func: Union[None, Callable] = None) -> Union[MultiCircuit, None]:
        """
        Load GridCal compatible file
        :param text_func: pointer to function that prints the names
        :param progress_func: pointer to function that prints the progress 0~100
        :return: MultiCircuit
        """
        self.logger = Logger()

        if isinstance(self.file_name, list):

            for f in self.file_name:
                _, file_extension = os.path.splitext(f)
                if file_extension.lower() not in ['.xml', '.zip']:
                    raise ValueError('Loading multiple files that are not XML/Zip (xml or zip is for CIM or CGMES)')

            data_parser = CgmesDataParser(text_func=text_func, progress_func=progress_func, logger=self.cgmes_logger)
            data_parser.load_files(files=self.file_name)
            self.cgmes_circuit = CgmesCircuit(cgmes_version=data_parser.cgmes_version, text_func=text_func,
                                              progress_func=progress_func, logger=self.cgmes_logger)
            self.cgmes_circuit.parse_files(data_parser=data_parser)
            self.circuit = cgmes_to_gridcal(cgmes_model=self.cgmes_circuit, logger=self.cgmes_logger)
        else:

            if os.path.exists(self.file_name):
                name, file_extension = os.path.splitext(self.file_name)
                # print(name, file_extension)
                if file_extension.lower() in ['.xls', '.xlsx']:

                    data_dictionary = load_from_xls(self.file_name)

                    # Pass the table-like data dictionary to objects in this circuit
                    if 'version' not in data_dictionary:
                        interpret_data_v1(self.circuit, data_dictionary, self.logger)

                    elif data_dictionary['version'] == 2.0:
                        self.circuit = MultiCircuit()
                        interprete_excel_v2(self.circuit, data_dictionary)

                    elif data_dictionary['version'] == 3.0:
                        self.circuit = MultiCircuit()
                        interpret_excel_v3(self.circuit, data_dictionary)

                    elif data_dictionary['version'] == 4.0:
                        if data_dictionary is not None:
                            self.circuit = parse_gridcal_data(data=data_dictionary,
                                                              text_func=text_func,
                                                              progress_func=progress_func,
                                                              logger=self.logger)
                        else:
                            self.logger.add("Error while reading the file :(")
                            return None
                    else:
                        self.logger.add('The file could not be processed')

                elif file_extension.lower() in ['.gridcal', '.dgridcal']:

                    # open file content
                    data_dictionary, self.json_files = get_frames_from_zip(self.file_name,
                                                                           text_func=text_func,
                                                                           progress_func=progress_func,
                                                                           logger=self.logger)
                    # interpret file content
                    if data_dictionary is not None:
                        self.circuit = parse_gridcal_data(data=data_dictionary,
                                                          text_func=text_func,
                                                          progress_func=progress_func,
                                                          logger=self.logger)
                    else:
                        self.logger.add("Error while reading the file :(")
                        return None

                elif file_extension.lower() == '.sqlite':

                    # open file content
                    data_dictionary = open_data_frames_from_sqlite(self.file_name,
                                                                   text_func=text_func,
                                                                   progress_func=progress_func)
                    # interpret file content
                    if data_dictionary is not None:
                        self.circuit = parse_gridcal_data(data_dictionary, logger=self.logger)
                    else:
                        self.logger.add("Error while reading the file :(")
                        return None

                elif file_extension.lower() == '.dgs':
                    self.circuit = dgs_to_circuit(self.file_name)

                elif file_extension.lower() == '.gch5':
                    self.circuit = open_h5(self.file_name, text_func=text_func, prog_func=progress_func)

                elif file_extension.lower() == '.m':
                    self.circuit, log = parse_matpower_file(self.file_name)
                    self.logger += log

                elif file_extension.lower() == '.dpx':
                    self.circuit, log = load_dpx(self.file_name)
                    self.logger += log

                elif file_extension.lower() == '.json':

                    # the json file can be the GridCal one or the iPA one...
                    with open(self.file_name, encoding="utf-8") as f:
                        data = json.load(f)

                        if isinstance(data, dict):
                            if 'Red' in data.keys():
                                self.circuit = load_iPA(self.file_name)
                            elif sum([x in data.keys() for x in ['type', 'version']]) == 2:
                                version = int(float(data['version']))

                                if data['type'] == 'Grid Exchange Json File' and 'profiles' in data.keys():
                                    if version == 2:
                                        self.circuit = parse_json_data_v2(data, self.logger)

                                    elif version == 3:
                                        self.circuit = parse_json_data_v3(data, self.logger)
                                    else:
                                        self.logger.add_error('Recognised as a gridCal compatible Json '
                                                              'but the version is not supported')

                            else:
                                self.logger.add_error('Unknown json format')

                        elif isinstance(data, list):
                            self.circuit = parse_json(self.file_name)

                        else:
                            self.logger.add_error('Unknown json format')

                elif file_extension.lower() == '.ejson3':
                    with open(self.file_name, encoding="utf-8") as f:
                        data = json.load(f)
                        self.circuit = parse_json_data_v3(data, self.logger)

                elif file_extension.lower() == '.raw':
                    pss_grid = read_raw(self.file_name,
                                        text_func=text_func,
                                        progress_func=progress_func,
                                        logger=self.logger)
                    self.circuit = psse_to_gridcal(psse_circuit=pss_grid, logger=self.logger)

                elif file_extension.lower() == '.rawx':
                    pss_grid = parse_rawx(self.file_name, logger=self.logger)
                    self.circuit = psse_to_gridcal(psse_circuit=pss_grid, logger=self.logger)

                elif file_extension.lower() == '.epc':
                    parser = PowerWorldParser(self.file_name)
                    self.circuit = parser.circuit
                    self.logger += parser.logger

                elif file_extension.lower() in ['.xml', '.zip']:
                    data_parser = CgmesDataParser(text_func=text_func, progress_func=progress_func,
                                                  logger=self.cgmes_logger)
                    data_parser.load_files(files=[self.file_name])

                    if is_valid_cgmes(data_parser.cgmes_version):
                        self.cgmes_circuit = CgmesCircuit(cgmes_version=data_parser.cgmes_version, text_func=text_func,
                                                          progress_func=progress_func, logger=self.cgmes_logger)
                        self.cgmes_circuit.parse_files(data_parser=data_parser)
                        self.circuit = cgmes_to_gridcal(cgmes_model=self.cgmes_circuit, logger=self.cgmes_logger)
                    else:
                        # try CIM
                        parser = CIMImport(text_func=text_func, progress_func=progress_func)
                        self.circuit = parser.load_cim_file(self.file_name)
                        self.logger += parser.logger

                elif file_extension.lower() == '.hdf5':
                    self.circuit = parse_hdf5(self.file_name, self.logger)

                elif file_extension.lower() == '.nc':
                    self.circuit = parse_netcdf(self.file_name, self.logger)

            else:
                # warn('The file does not exist.')
                self.logger.add_error('Does not exist', self.file_name)

        return self.circuit

    def check_json_type(self, file_name):
        """
        Check the json file type from its internal data
        :param file_name: file path
        :return: data['type'] | 'Not json file' | 'Unknown json file'
        """

        if not os.path.exists(file_name):
            return 'Not json file'

        _, file_extension = os.path.splitext(file_name)

        if file_extension.lower() == '.json':
            with open(self.file_name, encoding="utf-8") as f:
                data = json.load(f)
                return data['type'] if 'type' in data else 'Unknown json file'
        else:
            return 'Not json file'


class FileSave:
    """
    FileSave
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 file_name: str,
                 options: FileSavingOptions = FileSavingOptions(),
                 text_func=None,
                 progress_func=None):
        """
        File saver
        :param circuit: MultiCircuit
        :param file_name: file name to save to
        :param options: FileSavingOptions
        :param text_func: Pointer to the text function
        :param progress_func: Pointer to the progress function
        """
        self.circuit = circuit

        self.file_name = file_name

        self.options = options

        self.text_func = text_func

        self.progress_func = progress_func

    def save(self) -> Logger:
        """
        Save the file in the corresponding format
        :return: logger with information
        """
        if self.file_name.endswith('.xlsx'):
            logger = self.save_excel()

        elif self.file_name.endswith('.gridcal') or self.file_name.endswith('.dgridcal'):
            logger = self.save_zip()

        elif self.file_name.endswith('.sqlite'):
            logger = self.save_sqlite()

        elif self.file_name.endswith('.ejson3'):
            logger = self.save_json_v3()

        elif self.file_name.endswith('.zip') and "CGMES" in self.options.type_selected:
            logger = self.save_cgmes()

        elif self.file_name.endswith('.xml') and "CIM" in self.options.type_selected:
            logger = self.save_cim()

        elif self.file_name.endswith('.gch5'):
            logger = self.save_h5()

        elif self.file_name.endswith('.rawx'):
            logger = self.save_rawx()

        elif self.file_name.endswith('.raw'):
            logger = self.save_raw()

        elif self.file_name.endswith('.newton'):
            logger = self.save_newton()

        elif self.file_name.endswith('.pgm'):
            logger = self.save_pgm()

        else:
            logger = Logger()
            logger.add_error('File path extension not understood', self.file_name)

        return logger

    def save_excel(self) -> Logger:
        """
        Save the circuit information in excel format
        :return: logger with information
        """

        logger = save_excel(self.circuit, self.file_name)

        return logger

    def save_zip(self) -> Logger:
        """
        Save the circuit information in zip format
        :return: logger with information
        """

        logger = Logger()

        dfs = gather_model_as_data_frames(self.circuit,
                                          legacy=False)

        model_data = gather_model_as_jsons(self.circuit)

        save_gridcal_data_to_zip(dfs=dfs,
                                 filename_zip=self.file_name,
                                 model_data=model_data,
                                 sessions_data=self.options.sessions_data,
                                 diagrams=self.circuit.diagrams,
                                 json_files=self.options.dictionary_of_json_files,
                                 text_func=self.text_func,
                                 progress_func=self.progress_func,
                                 logger=logger)

        return logger

    def save_sqlite(self) -> Logger:
        """
        Save the circuit information in sqlite
        :return: logger with information
        """

        logger = Logger()

        dfs = gather_model_as_data_frames(self.circuit)

        save_data_frames_to_sqlite(dfs,
                                   file_path=self.file_name,
                                   text_func=self.text_func,
                                   progress_func=self.progress_func)

        return logger

    def save_json_v3(self) -> Logger:
        """
        Save the circuit information in json format
        :return:logger with information
        """

        logger = save_json_file_v3(self.file_name,
                                   self.circuit,
                                   self.options.simulation_drivers)
        return logger

    def save_cim(self) -> Logger:
        """
        Save the circuit information in CIM format
        :return: logger with information
        """

        cim = CIMExport(self.circuit)
        cim.save(file_name=self.file_name)

        return cim.logger

    def save_cgmes(self) -> Logger:
        """
        Save the circuit information in CGMES format
        :return: logger with information
        """
        logger = Logger()
        if self.options.cgmes_boundary_set == "":
            logger.add_error(msg="Missing Boundary set path.")
            return logger
        # CGMES version should be given in the settings
        cgmes_circuit = CgmesCircuit(cgmes_version=self.options.cgmes_version,
                                     text_func=self.text_func,
                                     progress_func=self.progress_func, logger=logger)

        data_parser = CgmesDataParser(text_func=self.text_func,
                                      progress_func=self.progress_func,
                                      logger=logger)
        data_parser.load_files(files=[self.options.cgmes_boundary_set])
        cgmes_circuit.parse_files(data_parser=data_parser)
        profiles_to_export = self.options.cgmes_profiles
        one_file_per_profile = self.options.one_file_per_profile
        pf_results = self.options.get_power_flow_results()
        cgmes_circuit = gridcal_to_cgmes(gc_model=self.circuit,
                                         cgmes_model=cgmes_circuit,
                                         pf_results=pf_results,
                                         logger=logger)
        cgmes_circuit = create_cgmes_headers(cgmes_model=cgmes_circuit,
                                             profiles_to_export=profiles_to_export,
                                             version="1",
                                             desc="Test description.",
                                             scenariotime="2021-02-09T19:30:00Z")

        cim_exporter = CimExporter(cgmes_circuit=cgmes_circuit,
                                   profiles_to_export=profiles_to_export,
                                   one_file_per_profile=one_file_per_profile)
        cim_exporter.export(self.file_name)

        return logger

    def save_h5(self) -> Logger:
        """
        Save the circuit information in CIM format
        :return: logger with information
        """

        logger = save_h5(self.circuit, self.file_name,
                         text_func=self.text_func,
                         prog_func=self.progress_func)

        return logger

    def save_raw(self) -> Logger:
        """
        Save the circuit information in json format
        :return:logger with information
        """
        logger = Logger()
        raw_circuit = gridcal_to_raw(self.circuit, logger=logger)
        logger += write_raw(self.file_name, raw_circuit)
        return logger

    def save_rawx(self) -> Logger:
        """
        Save the circuit information in json format
        :return:logger with information
        """
        logger = Logger()
        raw_circuit = gridcal_to_raw(self.circuit, logger=logger)
        logger += write_rawx(self.file_name, raw_circuit)
        return logger

    def save_newton(self) -> Logger:
        """
        Save the circuit information in sqlite
        :return: logger with information
        """
        from GridCalEngine.Compilers.circuit_to_newton_pa import to_newton_pa, npa
        logger = Logger()

        time_series = self.circuit.time_profile is not None

        if time_series:
            tidx = list(range(len(self.circuit.time_profile)))
        else:
            tidx = None

        newton_grid, _ = to_newton_pa(self.circuit, use_time_series=time_series, time_indices=tidx)

        npa.FileHandler().save(newton_grid, self.file_name)

        return logger

    def save_pgm(self) -> Logger:
        """
        Save to Power Grid Model format
        :return: logger with information
        """
        from GridCalEngine.Compilers.circuit_to_pgm import save_pgm
        logger = Logger()

        save_pgm(filename=self.file_name, circuit=self.circuit, logger=logger, time_series=self.circuit.has_time_series)

        return logger
