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
import os
import scipy.sparse as sp
from GridCalEngine.api import *


def test_numerical_cicuit_generator_contingencies():
    """
    Check whether the generator contingency present on the gridcal file is applied correctly
    This test compares the generator active power with the expected power when applying the contingency.
    :return: Nothing if ok, fails if not
    """
    for i, fname in enumerate([
        os.path.join('data', 'grids', 'IEEE14-gen120.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-gen80.gridcal')
    ]):
        main_circuit = FileOpen(fname).open()
        nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

        # for cnt in main_circuit.contingencies:
        #
        #     nc.set_contingency_status(contingencies_list=[cnt])

        # yo sé que la primera contingencia es cambiar el generador del bus 1 en 120%
        cnt = main_circuit.contingencies[0]

        p_prev = nc.generator_data.p[1]  # P del primer generador antes del cambio
        nc.set_contingency_status(contingencies_list=[cnt])
        p_post = nc.generator_data.p[1]
        change = 1.2 if i == 0 else 0.8

        assert p_prev * change == p_post


def test_numerical_cicuit_branch_contingencies():
    """
    Check whether the branch contingency present on the gridcal file is applied correctly
    This test compares the number of contingencies with the number of deactivated branches.
    :return: Nothing if ok, fails if not
    """
    for i, fname in enumerate([
        os.path.join('data', 'grids', 'IEEE14-13_14.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-2_4_1-3_4_1.gridcal')
    ]):
        main_circuit = FileOpen(fname).open()
        nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

        cnt = main_circuit.contingencies
        nc.set_contingency_status(contingencies_list=cnt)
        cnt_branch = np.where(nc.branch_data.active == 0)[0]  # deactivated branches

        assert len(cnt_branch) == len(cnt)


def test_numerical_cicuit_spv():
    """
    Check that the numerical circuit does apply a generator contingency correctly
    """
    fname_cont = os.path.join('data', 'grids', 'IEEE14-gen120.gridcal')

    main_circuit = FileOpen(fname_cont).open()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    # for cnt in main_circuit.contingencies:
    #
    #     nc.set_contingency_status(contingencies_list=[cnt])

    cnt = main_circuit.contingencies[0]  # yo sé que la primera contingencia es cambiar el generador del bus 1 en 120%

    p_antes = nc.generator_data.p[1]  # P del primer generador antes del cambio
    nc.set_contingency_status(contingencies_list=[cnt])
    p_despues = nc.generator_data.p[1]

    assert p_antes * 1.20 == p_despues


def test_bus_indexing_remap():
    def get_bus_indices(C_branch_bus: sp.csc_matrix):
        """

        :param C_branch_bus:
        :return:
        """
        assert (isinstance(C_branch_bus, sp.csc_matrix))
        F = np.zeros(C_branch_bus.shape[0], dtype=int)

        for j in range(C_branch_bus.shape[1]):
            for l in range(C_branch_bus.indptr[j], C_branch_bus.indptr[j + 1]):
                i = C_branch_bus.indices[l]  # row index
                F[i] = j

        return F

    fname_cont = os.path.join('data', 'grids', 'IEEE14 - multi-island hvdc.gridcal')

    main_circuit = FileOpen(fname_cont).open()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    islands = nc.split_into_islands()

    for island in islands:

        # old way of finding the F and T arrays of an island
        F = get_bus_indices(island.branch_data.C_branch_bus_f.tocsc())
        T = get_bus_indices(island.branch_data.C_branch_bus_t.tocsc())

        assert np.allclose(F, island.branch_data.F)
        assert np.allclose(T, island.branch_data.T)
