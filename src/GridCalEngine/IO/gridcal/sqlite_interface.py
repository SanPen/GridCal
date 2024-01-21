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
import pandas as pd
import sqlite3

from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.excel_interface import check_names
from GridCalEngine.IO.gridcal.generic_io_functions import parse_config_df


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

