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
from scipy.sparse import diags
from GridCal.Engine import *


def __check__(fname):
    """
    Check that Ybus = Yseries + Yshunt
    :param fname: name of the GridCal file
    :return: True if succeeded, exception otherwise
    """
    # load the file
    main_circuit = FileOpen(fname).open()

    # compile the data
    numerical_circuit = main_circuit.compile_snapshot()

    # split into the possible islands
    islands = numerical_circuit.compute()

    # check the consistency of each island
    for island in islands:
        assert ((island.Ybus - (island.Yseries + diags(island.Ysh_helm))).data < 1e-9).all()

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
