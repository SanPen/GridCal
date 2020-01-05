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
import sqlite3
import numpy as np

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.excel_interface import check_names
from GridCal.Engine.IO.generic_io_functions import parse_config_df


def save_data_frames_to_sqlite(dfs, file_path, text_func=None, progress_func=None):
    """
    Save the circuit information in excel format
    :param dfs: list of DataFrames
    :param file_path: path to the excel file
    :return: logger with information
    """
    logger = Logger()

    conn = sqlite3.connect(file_path)

    n = len(dfs.keys())

    for i, key in enumerate(dfs.keys()):

        if progress_func is not None:
            progress_func((i + 1) / n * 100)

        if text_func is not None:
            text_func('Saving ' + key)

        dfs[key].to_sql(key, conn, if_exists='replace', index=False)

    return logger


def open_data_frames_from_sqlite(file_path, text_func=None, progress_func=None):

    # make connection
    conn = sqlite3.connect(file_path)

    dfs = dict()

    # get the table names
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")

    names = [t[0] for t in tables]

    check_names(names)
    n = len(names)
    for i, key in enumerate(names):

        if progress_func is not None:
            progress_func((i + 1) / n * 100)

        if text_func is not None:
            text_func('select * from ' + key)

        dfs[key] = pd.read_sql('select * from ' + key, conn)

    # parse the configuration
    dfs = parse_config_df(dfs['config'], dfs)

    return dfs


if __name__ == '__main__':
    import time
    from GridCal.Engine.IO.file_handler import *
    from GridCal.Engine.IO.pack_unpack import create_data_frames, data_frames_to_circuit

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'

    a = time.time()
    circuit_ = FileOpen(fname).open()
    print('native based open:', time.time() - a)

    print('Saving .sqlite ...')
    dfs = dfs = create_data_frames(circuit=circuit_)
    save_data_frames_to_sqlite(dfs, file_path=circuit_.name + '.sqlite')

    a = time.time()
    data = open_data_frames_from_sqlite(circuit_.name + '.sqlite')
    circuit2 = data_frames_to_circuit(data)
    print('sql based open:', time.time() - a)
