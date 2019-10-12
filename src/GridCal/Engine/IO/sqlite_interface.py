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
from GridCal.Engine.IO.excel_interface import create_data_frames, interpret_excel_v3, check_names


def save_sqlite(circuit: MultiCircuit, file_path):
    """
    Save the circuit information in excel format
    :param circuit: MultiCircuit instance
    :param file_path: path to the excel file
    :return: logger with information
    """
    logger = Logger()

    dfs = create_data_frames(circuit=circuit)

    conn = sqlite3.connect(file_path)

    for key in dfs.keys():
        dfs[key].to_sql(key, conn, if_exists='replace', index=True)

    return logger


def open_sqlite(file_path):

    circuit = MultiCircuit()

    # make connection
    conn = sqlite3.connect(file_path)

    dfs = dict()

    # get the table names
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")

    names = [t[0] for t in tables]

    check_names(names)

    for key in names:
        dfs[key] = pd.read_sql('select * from ' + key, conn)

    df = dfs['config']
    idx = df['Property'][df['Property'] == 'BaseMVA'].index
    if len(idx) > 0:
        dfs["baseMVA"] = np.double(df.values[idx, 1])
    else:
        dfs["baseMVA"] = 100

    idx = df['Property'][df['Property'] == 'Version'].index
    if len(idx) > 0:
        dfs["version"] = np.double(df.values[idx, 1])

    idx = df['Property'][df['Property'] == 'Name'].index
    if len(idx) > 0:
        dfs["name"] = df.values[idx[0], 1]
    else:
        dfs["name"] = 'Grid'

    idx = df['Property'][df['Property'] == 'Comments'].index
    if len(idx) > 0:
        dfs["Comments"] = df.values[idx[0], 1]
    else:
        dfs["Comments"] = ''

    # fill circuit data
    interpret_excel_v3(circuit, dfs)

    return circuit


if __name__ == '__main__':
    import time
    from GridCal.Engine.IO.file_handler import *

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/src/GridCal/Monash.xlsx'

    a = time.clock()
    circuit = FileOpen(fname).open()
    print('excel based open:', time.clock() - a)

    save_sqlite(circuit, file_path='1354 pegase.sqlite')

    a = time.clock()
    circuit2 = open_sqlite('1354 pegase.sqlite')
    print('sql based open:', time.clock() - a)
