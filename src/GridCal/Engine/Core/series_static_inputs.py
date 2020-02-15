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

import numpy as np
import pandas as pd
from scipy.sparse import diags, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import factorized
from scipy.sparse import csc_matrix


class StaticSeriesIslandInputs:
    """
    This class represents a StaticSeriesInputs for a single island
    """
    def __init__(self):
        pass


class StaticSeriesInputs:
    """
    This class represents the set of numerical inputs for simulations that require
    static values from the time series mode (power flow time series, monte carlo, PTDF time-series, etc.)
    """
    def __init__(self):
        pass


