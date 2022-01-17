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
import os
import collections
import h5py
import pandas as pd
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.IO.pack_unpack import create_data_frames, data_frames_to_circuit
from GridCal.Engine.Core.multi_circuit import MultiCircuit


def save_h5(circuit: MultiCircuit, file_path, compression_opts=5, text_func=None, prog_func=None):
    """
    Save the circuit information in excel format
    :param circuit: MultiCircuit instance
    :param file_path: path to the excel file
    :param compression_opts: compression [0, 9]
    :param text_func:
    :param prog_func:
    :return: logger with information
    """
    logger = Logger()

    dfs = create_data_frames(circuit=circuit)

    n = len(dfs)
    i = 0
    for key, df in dfs.items():

        if text_func:
            text_func('Saving ' + key + '...')

        df.to_hdf(file_path, key=key, complevel=compression_opts, complib='zlib')

        if prog_func:
            prog_func((i+1) / n * 100)

        i += 1

    return logger


def open_h5(file_path, text_func=None, prog_func=None):
    """

    :param file_path:
    :param text_func:
    :param prog_func:
    :return:
    """
    store = pd.HDFStore(file_path)

    dfs = dict()
    n = len(list(store.root))
    i = 0
    for group in store.root:

        if text_func:
            text_func('Loading ' + group._v_name + '...')

        dfs[group._v_name] = pd.read_hdf(store, group._v_pathname)

        if prog_func:
            prog_func((i+1) / n * 100)
        i += 1

    store.close()

    circuit = data_frames_to_circuit(dfs)

    return circuit


if __name__ == '__main__':

    from GridCal.Engine.IO.file_handler import FileOpen

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    fname = '/home/santi/Documentos/REE/Debug/Propuesta_2026_v16_con MAR+operabilidad/Propuesta_2026_v16_con MAR+operabilidad.gridcal'

    print('First opening...')
    circuit = FileOpen(fname).open()

    print('Saving...')
    save_h5(circuit, file_path='test.gch5')

    print('Reopening')
    circuit2 = open_h5('test.gch5')
