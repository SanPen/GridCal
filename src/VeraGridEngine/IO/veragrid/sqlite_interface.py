# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import pandas as pd
import sqlite3

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.veragrid.excel_interface import check_names
from VeraGridEngine.IO.veragrid.generic_io_functions import parse_config_df


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

