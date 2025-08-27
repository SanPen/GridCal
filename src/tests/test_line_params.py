# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import VeraGridEngine.api as gce


def test_line_parameters():
    """
    Simple test that checks the conversion from ohm values to per unit
    :return:
    """

    b1 = gce.Bus(name="B1", Vnom=230.0)
    b2 = gce.Bus(name="B2", Vnom=230.0)

    # ohmic values
    r_ohm = [5.29, 8.993, 16.928, 20.631, 4.4965, 6.2951]
    x_ohm = [44.965, 48.668, 85.169, 89.93, 38.088, 53.3232]
    b_uS = [332.7, 298.69, 578.45, 676.75, 281.66, 395.08]

    # tes per-unit values
    r = [0.01, 0.017, 0.032, 0.039, 0.0085, 0.0119]
    x = [0.085, 0.092, 0.161, 0.17, 0.072, 0.1008]
    b_2 = [0.088, 0.079, 0.153, 0.179, 0.0745, 0.1045]

    wf = 2 * np.pi * 50

    for i in range(6):
        l1 = gce.Line(name="line 4-5", bus_from=b1, bus_to=b2)
        l1.fill_design_properties(r_ohm=r_ohm[i],
                                  x_ohm=x_ohm[i],
                                  c_nf=b_uS[i] * 1e3 / wf,
                                  length=1.0,
                                  Imax=1.0,
                                  Sbase=100.0,
                                  freq=50.0,
                                  apply_to_profile=False)

        assert np.allclose(l1.R, r[i], atol=1e-4)
        assert np.allclose(l1.X, x[i], atol=1e-4)
        assert np.allclose(l1.B / 2, b_2[i], atol=1e-4)
