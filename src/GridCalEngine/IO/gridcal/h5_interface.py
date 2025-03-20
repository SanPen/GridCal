# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import pandas as pd
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.pack_unpack import gather_model_as_data_frames, parse_gridcal_data
from GridCalEngine.Devices.multi_circuit import MultiCircuit


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

    dfs = gather_model_as_data_frames(circuit=circuit, logger=logger, legacy=True)

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


def open_h5(file_path, text_func=None, prog_func=None, logger: Logger = Logger()):
    """

    :param file_path:
    :param text_func:
    :param prog_func:
    :param logger:
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

    circuit = parse_gridcal_data(dfs, logger=logger)

    return circuit

