# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
from scipy.sparse import diags
from GridCalEngine.api import *


def __check__(fname):
    """
    Check that Ybus = Yseries + Yshunt
    :param fname: name of the GridCal file
    :return: True if succeeded, exception otherwise
    """
    # load the file
    main_circuit = FileOpen(fname).open()

    # compile the data
    numerical_circuit = compile_numerical_circuit_at(main_circuit, apply_temperature=False)

    # split into the possible islands
    islands = numerical_circuit.split_into_islands()

    # check the consistency of each island
    for island in islands:

        adm = island.get_admittance_matrices()
        adms = island.get_series_admittance_matrices()

        assert ((adm.Ybus - (adms.Yseries + diags(adms.Yshunt))).data < 1e-9).all()

    return True


def test1():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids', 'IEEE 30 Bus with storage.xlsx')
    res = __check__(fname)
    return res


def test2():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids',  'Brazil11_loading05.gridcal')
    res = __check__(fname)
    return res


def test3():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids', "Iwamoto's 11 Bus.xlsx")
    res = __check__(fname)
    return res


if __name__ == '__main__':

    test3()
