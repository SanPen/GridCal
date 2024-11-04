# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
