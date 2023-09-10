# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import numpy as np


def slice_to_range(sl: slice, n):
    """
    Turn a slice into a range
    :param sl: slice object
    :param n: total number of items
    :return: range object, if the slice is not supported an exception is raised
    """
    if sl.start is None and sl.step is None and sl.start is None:  # (:)
        return range(n)

    elif sl.start is not None and sl.step is None and sl.start is None:  # (a:)
        return range(sl.start, n)

    elif sl.start is not None and sl.step is not None and sl.start is None:  # (?)
        raise Exception('Invalid slice')
    elif sl.start is not None and sl.step is None and sl.start is not None:  # (a:b)
        return range(sl.start, sl.stop)

    elif sl.start is not None and sl.step is not None and sl.start is not None:  # (a:s:b)
        return range(sl.start, sl.stop, sl.step)

    elif sl.start is None and sl.step is None and sl.start is not None:  # (:b)
        return range(sl.stop)

    else:
        raise Exception('Invalid slice')


def dense_to_str(mat: np.ndarray):
    """
    Turn dense 2D numpy array into a string
    :param mat: 2D numpy array
    :return: string
    """
    rows, cols = mat.shape
    val = "Matrix (" + ("%d" % rows) + " x " + ("%d" % cols) + ")\n"
    val += str(mat).replace('. ', ' ').replace('[', ' ').replace(']', '').replace('0 ', '_ ').replace('0.', '_ ')
    # for i in range(0, rows):
    #     for j in range(0, cols):
    #         x = mat[i, j]
    #         if x is not None:
    #             if x == 0:
    #                 val += '{:<4}'.format(0)
    #             else:
    #                 val += '{:<4}'.format(x)
    #         else:
    #             val += ""
    #     val += '\n'

    # for rows in M:
    #     print(*['{:<4}'.format(each) for each in rows])

    return val

