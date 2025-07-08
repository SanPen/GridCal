# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import numpy as np
from scipy.optimize import newton_krylov
from GridCalEngine.Utils.Symbolic import BlockSolver


def initialize(system: BlockSolver, guess: list(), method: str)-> np.ndarray:
    init_values = np.empty(system._n_vars)
    if method == 'Newton-Krylov':
        init_values = init_newton_krylov(system, guess)
        return init_values

    raise ValueError(f"Unknown method '{method}'")



def init_newton_krylov(system: BlockSolver, guess) -> np.ndarray:
    state_eqs, algeb_eqs = system.equations()
    equations = state_eqs + algeb_eqs
    pdb.set_trace()
    #equations = np.array(state_eqs + algeb_eqs)

    def F(x):
        return np.array(equations)

    init_values = newton_krylov(F, guess.tolist(), method='gmres', verbose=1)

    return init_values
