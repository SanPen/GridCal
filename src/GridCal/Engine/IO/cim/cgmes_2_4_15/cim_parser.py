# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from typing import Callable, List
from GridCal.Engine.data_logger import DataLogger
from GridCal.Engine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit
from GridCal.Engine.IO.cim.cim_data_parser import CimDataParser


def read_cgmes_files(cim_files: List[str],
                     logger: DataLogger = DataLogger(),
                     progress_func: Callable = None,
                     text_func: Callable = None) -> CgmesCircuit:
    """

    :param cim_files:
    :param logger:
    :param progress_func:
    :param text_func:
    :return:
    """

    # declare CIM circuit to process the file(s)
    cim = CgmesCircuit(text_func=text_func, progress_func=progress_func, logger=logger)

    # read the data
    data_parser = CimDataParser(text_func=text_func, progress_func=progress_func, logger=logger)
    data_parser.load_cim_file(cim_files=cim_files)
    cim.set_cim_data(data_parser.cim_data)

    # replace CIM references in the CIM objects
    if text_func:
        text_func('Consolidating CIM information...')
    cim.consolidate()

    if text_func:
        text_func('Detecting circular references...')
        cim.detect_circular_references()

    if text_func:
        text_func('Done!')

    return cim


if __name__ == '__main__':
    import os

    # folder = r'C:\Users\penversa\Documents\Grids\CGMES\TYNDP_2025'
    folder = '/home/santi/Documentos/Private_Grids/CGMES/TYNDP_2025'

    files = [
        # '2025NT_FR_model_004.zip',
        # '2025NT_ES_model_003.zip',
        '2025NT_PT_model_003.zip',
        '20191017T0918Z_ENTSO-E_BD_1130.zip'
    ]
    fnames = [os.path.join(folder, f) for f in files]

    print('Reading...')
    cgmes_circuit_ = read_cgmes_files(fnames)
    print()
    cgmes_circuit_.to_excel('Spain_data.xlsx')
