import timeit
import os
import numpy as np
from scipy import sparse as sp
from scipy.sparse import csc_matrix
import GridCalEngine.api as gce
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at


def test_csc_speeds():

    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case300.m')

    grid = gce.FileOpen(file_path).open()

    csh = gce.ControllableShunt(name="Cshunt", number_of_steps=2, b_per_step=15.0)
    grid.add_controllable_shunt(bus=grid.buses[3], api_obj=csh)
    grid.generators[5].enabled_dispatch = False

    nc = compile_numerical_circuit_at(grid)


    id_sh = np.where(nc.shunt_data.controllable == True)[0]
    sh_bus_idx = nc.shunt_data.get_bus_indices()[id_sh]
    nsh = len(id_sh)
    ngen = len(nc.generator_data.pmax)

    gen_bus_idx = np.r_[nc.generator_data.get_bus_indices(), sh_bus_idx]
    gen_disp_idx = np.r_[nc.generator_data.get_dispatchable_active_indices(), np.arange(ngen, ngen + nsh)]

    t_1s = timeit.default_timer()

    Csh = nc.shunt_data.get_C_bus_elm()[:, id_sh]
    Cgen = nc.generator_data.get_C_bus_elm()

    Cg = sp.hstack([Cgen, Csh])

    t_1e = timeit.default_timer()

    nbus = nc.nbus
    ngendisp = len(gen_disp_idx)

    t_2s = timeit.default_timer()

    b = csc_matrix((np.ones(ngendisp), (gen_bus_idx, np.arange(ngendisp))), shape = (nbus, ngendisp))

    t_2e = timeit.default_timer()

    print(f'{t_1e - t_1s}\n')
    print(f'{t_2e - t_2s}\n ')

if __name__ == '__main__':
    test_csc_speeds()