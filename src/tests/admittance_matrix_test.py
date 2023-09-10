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
from scipy.sparse import diags
from GridCalEngine import *


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
        assert ((island.Ybus - (island.Yseries + diags(island.Yshunt))).data < 1e-9).all()

    return True


def test1():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    res = __check__(fname)
    return res


def test2():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'Brazil11_loading05.gridcal')
    res = __check__(fname)
    return res


def test3():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', "Iwamoto's 11 Bus.xlsx")
    res = __check__(fname)
    return res


if __name__ == '__main__':

    test3()
