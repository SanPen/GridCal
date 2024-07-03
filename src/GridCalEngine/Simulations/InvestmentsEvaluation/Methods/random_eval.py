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
import numpy as np


def random_trial(obj_func,
                 n_var: int = 1,
                 n_obj: int = 2,
                 max_evals: int = 3000):
    """

    :param obj_func:
    :param n_var:
    :param n_obj:
    :param max_evals:
    :return:
    """

    # Generate sampling rule
    num_ones = np.linspace(0, n_var, max_evals, dtype=int)
    num_ones[-1] = n_var
    ones_into_array = np.zeros((max_evals, n_var), dtype=int)
    # Fill ones_into_array randomly
    for i, num in enumerate(num_ones):
        ones_into_array[i, :num] = 1
        np.random.shuffle(ones_into_array[i])

    # Init arrays to store results
    x = np.zeros((max_evals, n_var))
    f = np.zeros((max_evals, n_obj))

    # Compute objectives for each x combination
    for i, arr in enumerate(ones_into_array):
        x[i, :] = arr
        f[i, :] = obj_func(arr)

    import pandas as pd
    dff = pd.DataFrame(f)
    dff.to_excel('random_trial.xlsx')
    return x, f
