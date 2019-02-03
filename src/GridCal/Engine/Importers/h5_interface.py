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
import pandas as pd

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Importers.excel_interface import create_data_frames, interpret_excel_v3


def save_h5(circuit: MultiCircuit, file_path):
    """
    Save the circuit information in excel format
    :param circuit: MultiCircuit instance
    :param file_path: path to the excel file
    :return: logger with information
    """
    logger = list()

    dfs = create_data_frames(circuit=circuit)

    store = pd.HDFStore(file_path)

    for key in dfs.keys():
        store[key] = dfs[key]

    return logger


def open_h5(file_path):

    circuit = MultiCircuit()

    store = pd.HDFStore(file_path)

    dfs = dict()
    for group in store.root:
        dfs[group._v_name] = pd.read_hdf(store, group._v_pathname)

    return dfs


if __name__ == '__main__':

    from GridCal.Engine.Importers.file_handler import *

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    circuit = FileOpen(fname).open()

    save_h5(circuit, file_path='1354 pegase.h5')

    circuit2 = open_h5('1354 pegase.h5')
