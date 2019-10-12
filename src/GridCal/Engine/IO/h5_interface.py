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
import h5py
from h5py._hl.dataset import Dataset
from h5py._hl.group import Group
import pandas as pd
import numpy as np

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.excel_interface import create_data_frames, interpret_excel_v3


def save_h5(circuit: MultiCircuit, file_path):
    """
    Save the circuit information in excel format
    :param circuit: MultiCircuit instance
    :param file_path: path to the excel file
    :return: logger with information
    """
    logger = Logger()

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


def save_dict_to_hdf5(dic, filename):
    """

    :param dic:
    :param filename:
    :return:
    """
    with h5py.File(filename, 'w') as h5file:
        recursively_save_dict_contents_to_group(h5file, '/', dic)


def recursively_save_dict_contents_to_group(h5file, path, dic):
    """

    :param h5file:
    :param path:
    :param dic:
    :return:
    """
    for key, item in dic.items():
        if isinstance(item, (np.ndarray, np.int64, np.float64, str, bytes)):
            h5file[path + key] = item
        elif isinstance(item, dict):
            recursively_save_dict_contents_to_group(h5file, path + key + '/', item)
        else:
            raise ValueError('Cannot save %s type'%type(item))


def load_dict_from_hdf5(filename):
    """

    :param filename:
    :return:
    """
    with h5py.File(filename, 'r') as h5file:
        return recursively_load_dict_contents_from_group(h5file, '/')


def recursively_load_dict_contents_from_group(h5file, path):
    """

    :param h5file:
    :param path:
    :return:
    """
    ans = {}
    for key, item in h5file[path].items():
        if isinstance(item, Dataset):
            ans[key] = item.value
        elif isinstance(item, Group):
            ans[key] = recursively_load_dict_contents_from_group(h5file, path + key + '/')
    return ans


if __name__ == '__main__':

    from GridCal.Engine.IO.file_handler import *

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    circuit = FileOpen(fname).open()

    save_h5(circuit, file_path='1354 pegase.h5')

    circuit2 = open_h5('1354 pegase.h5')
