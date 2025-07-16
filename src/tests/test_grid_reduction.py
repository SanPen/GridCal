# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import GridCalEngine.api as gce


def test_ward_reduction():

    fname = os.path.join('data', 'grids', 'case89pegase.m')
    grid = gce.open_file(filename=fname)
