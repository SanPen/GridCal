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
from time import time
from scipy.sparse import csc_matrix, random, hstack, vstack

from GridCalEngine.Sparse.csc import csc_stack_2d_ff


def test_stack_4():
    """

    :return:
    """
    k = 1000
    l = 4 * k
    m = 6 * k

    A = csc_matrix(random(k, l, density=0.1))
    B = csc_matrix(random(k, k, density=0.1))
    C = csc_matrix(random(m, l, density=0.1))
    D = csc_matrix(random(m, k, density=0.1))
    t = time()
    E = hstack((vstack((A, C)), vstack((B, D))))
    print('Scipy\t', time() - t)

    t = time()
    E1 = csc_stack_2d_ff([A, B, C, D], 2, 2)
    print('Csparse3\t', time() - t)
    # print(A1)
    # print(B1)
    # print(C1)
    # print(D1)
    # print(E1)

    stack_test = (E.todense() == E1.todense()).all()

    print('Stacking pass:', stack_test)
    assert stack_test

    return True


if __name__ == '__main__':
    test_stack_4()
