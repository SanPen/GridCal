import timeit
import os
import numpy as np
import random
from scipy import sparse as sp
from scipy.sparse import csc_matrix, coo_matrix
import GridCalEngine.api as gce
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Utils.Sparse.csc import diags

#
# def test_average_speed_1(tries = 15, iter = 15):
#
#     t1 = 0
#     t2 = 0
#
#     cwd = os.getcwd()
#
#     # Go back two directories
#     new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
#
#     file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')
#
#     grid = gce.FileOpen(file_path).open()
#
#     nc = compile_numerical_circuit_at(grid)
#
#     nbus = nc.nbus
#     id_sh = np.where(nc.shunt_data.controllable == True)[0]
#     sh_bus_idx = nc.shunt_data.get_bus_indices()[id_sh]
#     nsh = len(id_sh)
#     ngen = len(nc.generator_data.pmax)
#
#     gen_bus_idx = np.r_[nc.generator_data.get_bus_indices(), sh_bus_idx]
#     gen_disp_idx = np.r_[nc.generator_data.get_dispatchable_active_indices(), np.arange(ngen, ngen + nsh)]
#
#     n_gen_disp_sh = len(gen_disp_idx)
#     n_gen_disp = n_gen_disp_sh - nsh
#
#     for i in range(tries):
#         t_1s = timeit.default_timer()
#
#         # Old operation
#         Csh = nc.shunt_data.get_C_bus_elm()[:, id_sh]
#         Cgen = nc.generator_data.get_C_bus_elm()
#
#         Cg = sp.hstack([Cgen, Csh])
#
#         for j in range(3 * iter): # This operation is repeated several times at each iteration
#             c_1 = Cg[:, gen_disp_idx]
#             c_1 = Cg[:, gen_disp_idx].T
#
#
#         t_1e = timeit.default_timer()
#
#         t1 += t_1e - t_1s
#
#         t_2s = timeit.default_timer()
#
#        # New operation
#         b = csc_matrix((np.ones(n_gen_disp_sh), (gen_bus_idx[gen_disp_idx], np.arange(n_gen_disp_sh))),
#                        shape=(nbus, n_gen_disp_sh))
#         b_t = b.T
#         t_2e = timeit.default_timer()
#
#         t2 += t_2e - t_2s
#
#     print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')
#
# def test_average_speed_2(tries = 15, iter = 15):
#
#     t1 = 0
#     t2 = 0
#     t3 = 0
#
#     cwd = os.getcwd()
#
#     # Go back two directories
#     new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
#
#     file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')
#
#     grid = gce.FileOpen(file_path).open()
#     for ll in range(len(grid.lines)):
#         grid.lines[ll].monitor_loading = True
#
#     nc = compile_numerical_circuit_at(grid)
#
#     nbr = nc.passive_branch_data.nelm
#     br_mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()
#     from_idx = nc.passive_branch_data.F
#     to_idx = nc.passive_branch_data.T
#     n_br_mon = len(br_mon_idx)
#     br_idx = np.arange(nbr)
#     admittances = nc.get_admittance_matrices()
#
#     for i in range(tries):
#         t_1s = timeit.default_timer()
#
#         # Old operation
#
#         for j in range(iter):
#             oldCf1 = admittances.Cf[br_mon_idx, :]
#             oldCf2 = admittances.Cf[br_mon_idx, :]
#             oldCf3 = admittances.Cf[br_mon_idx, :]
#             oldCf4 = admittances.Cf[br_mon_idx, :]
#             oldCf5 = admittances.Cf[br_mon_idx, :].T
#             oldCf6 = admittances.Cf[br_mon_idx, :].T
#
#             oldCt1 = admittances.Ct[br_mon_idx, :]
#             oldCt2 = admittances.Ct[br_mon_idx, :]
#             oldCt3 = admittances.Ct[br_mon_idx, :]
#             oldCt4 = admittances.Ct[br_mon_idx, :]
#             oldCt5 = admittances.Ct[br_mon_idx, :].T
#             oldCt6 = admittances.Ct[br_mon_idx, :].T
#
#
#         t_1e = timeit.default_timer()
#
#         t1 += t_1e - t_1s
#
#         ###################
#
#         t_2s = timeit.default_timer()
#
#        # New operation
#
#         newCf = nc.passive_branch_data.monitored_Cf(br_mon_idx)
#         newCf_t = newCf.T
#         newCt = nc.passive_branch_data.monitored_Ct(br_mon_idx)
#         newCt_t = newCt.T
#
#
#
#
#         t_2e = timeit.default_timer()
#
#         t2 += t_2e - t_2s
#
#         t_3s = timeit.default_timer()
#
#         # Alternative operation
#
#         newCf = admittances.Cf[br_mon_idx, :]
#         newCf_t = newCf.T
#         newCt = admittances.Ct[br_mon_idx, :]
#         newCt_t = newCt.T
#
#         t_3e = timeit.default_timer()
#
#         t3 += t_3e - t_3s
#
#
#     print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')
#     print(f'{(t3 - t2)  * 1000 / tries} miliseconds faster.')
#
#
# def test_average_speed_3(tries = 15, iter = 15):
#
#
#     t1 = 0
#     t2 = 0
#     t3 = 0
#
#     cwd = os.getcwd()
#
#     # Go back two directories
#     new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
#
#     file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')
#
#     grid = gce.FileOpen(file_path).open()
#     for ll in range(len(grid.lines)):
#         grid.lines[ll].monitor_loading = True
#
#     nc = compile_numerical_circuit_at(grid)
#
#     nbr = nc.passive_branch_data.nelm
#     br_mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()
#     from_idx = nc.passive_branch_data.F
#     to_idx = nc.passive_branch_data.T
#     n_br_mon = len(br_mon_idx)
#     br_idx = np.arange(nbr)
#     admittances = nc.get_admittance_matrices()
#     V = nc.bus_data.Vnom
#     Cf = nc.passive_branch_data.monitored_Cf(br_mon_idx)
#     Ct = nc.passive_branch_data.monitored_Ct(br_mon_idx)
#
#     for i in range(tries):
#
#         # Old operation
#         for j in range(iter):
#             t_1s = timeit.default_timer()
#
#             Vfmat = diags(Cf @ V)
#             Vtmat = diags(Ct @ V)
#
#             t_1e = timeit.default_timer()
#
#             t1 += t_1e - t_1s
#
#             ###################
#
#             t_2s = timeit.default_timer()
#
#            # New operation
#
#             Vfmat = diags(V[from_idx[br_mon_idx]])
#             Vtmat = diags(V[to_idx[br_mon_idx]])
#
#             t_2e = timeit.default_timer()
#
#             t2 += t_2e - t_2s
#
#     print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')

# def test_average_speed_4(tries = 15, iter = 15):
#
#
#     t1 = 0
#     t2 = 0
#     t3 = 0
#
#     cwd = os.getcwd()
#
#     # Go back two directories
#     new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
#
#     file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')
#
#     grid = gce.FileOpen(file_path).open()
#     for ll in range(len(grid.lines)):
#         grid.lines[ll].monitor_loading = True
#
#     nc = compile_numerical_circuit_at(grid)
#     nbus = nc.nbus
#
#     nbr = nc.passive_branch_data.nelm
#     br_mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()
#     from_idx = nc.passive_branch_data.F
#     to_idx = nc.passive_branch_data.T
#     n_br_mon = len(br_mon_idx)
#     br_idx = np.arange(nbr)
#     admittances = nc.get_admittance_matrices()
#     V = np.ones(nbus)* np.exp(1j * 0.001)
#     Cf = nc.passive_branch_data.monitored_Cf(br_mon_idx)
#     Ct = nc.passive_branch_data.monitored_Ct(br_mon_idx)
#     Vmat = diags(V)
#
#     for i in range(tries):
#         for j in range(iter):
#         # Old operation
#             t_1s = timeit.default_timer()
#
#             mat1 = admittances.Ybus @ V
#
#             t_1e = timeit.default_timer()
#             t1 += t_1e - t_1s
#
#             ###################
#            # New operation
#
#             t_2s = timeit.default_timer()
#
#             # data = admittances.Ybus.multiply(V).sum(axis=1).A1  # Extract result as a dense array
#
#             data = np.zeros(nbus)
#             for i in range(nbus):
#                 row_data = admittances.Ybus.data[admittances.Ybus.indptr[i]:admittances.Ybus.indptr[i + 1]]
#                 ids = admittances.Ybus.indices[admittances.Ybus.indptr[i]:admittances.Ybus.indptr[i + 1]]
#                 data[i] = np.sum(row_data * V[ids])
#
#             t_2e = timeit.default_timer()
#
#             t2 += t_2e - t_2s
#
#     print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')

    # Note to self: This tests shows that matrix to vector multiplication in the form of Ybus @ V seems the fastest way to do it.

# def test_average_speed_5(tries = 15, iter = 15):
#
#
#     t1 = 0
#     t2 = 0
#     t3 = 0
#
#     cwd = os.getcwd()
#
#     # Go back two directories
#     new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
#
#     file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')
#
#     grid = gce.FileOpen(file_path).open()
#     for ll in range(len(grid.lines)):
#         grid.lines[ll].monitor_loading = True
#
#     nc = compile_numerical_circuit_at(grid)
#     nbus = nc.nbus
#
#     admittances = nc.get_admittance_matrices()
#     Vm = np.random.rand(nbus)
#     V = Vm + 1j * np.random.rand(nbus)
#
#     Vmat = diags(V)
#     Ibus = admittances.Ybus @ V
#     IbusCJmat = diags(np.conj(Ibus))
#     vm_inv = diags(1 / Vm)
#     indptr = admittances.Ybus.indptr
#     indices = admittances.Ybus.indices
#     diag_ids = np.zeros(nbus, dtype=int)
#     cols, ids = admittances.Ybus.nonzero()
#
#     lam_p = np.ones(nbus)
#     lam_diag_p = diags(lam_p)
#
#     for i in range(nbus):
#         diag_ids[i] = np.where(indices[indptr[i]:indptr[i + 1]] == i)[0] + indptr[i]
#
#     for i in range(tries):
#         for j in range(iter):
#         # Old operation
#             t_1s = timeit.default_timer()
#             D_p = np.conj(admittances.Ybus).T @ Vmat
#             I_p = np.conj(Vmat) @ (D_p @ lam_diag_p - diags(D_p @ lam_p))
#
#             t_1e = timeit.default_timer()
#             t1 += t_1e - t_1s
#
#             ###################
#            # New operation
#
#             t_2s = timeit.default_timer()
#
#             data = np.conj(admittances.Ybus.data) * V[cols]
#             D_p2 = csc_matrix((data, (cols, indices)), shape=(nbus, nbus))
#             D_p3 = csc_matrix((data, (cols, indices)), shape=(nbus, nbus))
#             # D = sp.vstack([D_p2, D_p3])
#             D = sp.hstack([D_p2, D_p3])
#
#         # I_p2 = np.conj(Vmat) @ (D_p2 @ lam_diag_p - diags(D_p2 @ lam_p))
#
#             t_2e = timeit.default_timer()
#
#             t2 += t_2e - t_2s
#
#             t_3s = timeit.default_timer()
#
#             data = np.conj(admittances.Ybus.data) * V[cols]
#             D_p4 = coo_matrix((data, (cols, indices)), shape=(nbus, nbus))
#             D_p5 = coo_matrix((data, (cols, indices)), shape=(nbus, nbus))
#
#             # D = sp.vstack([D_p4, D_p5])
#             D = sp.hstack([D_p4, D_p5])
#             # I_p3 = np.conj(Vmat) @ (D_p3 @ lam_diag_p - diags(D_p3 @ lam_p))
#
#             t_3e = timeit.default_timer()
#
#             t3 += t_3e - t_3s
#
#
#
#     print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')
#     print(f'{(t2 - t3)  * 1000 / tries} miliseconds faster.')
    # Note to self: CSC hstack performance is way better than COO, while for vstack performance, COO performs marginally better.

def test_average_speed_6(tries = 15, iter = 15):


    t1 = 0
    t2 = 0
    t3 = 0

    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    for ll in range(len(grid.lines)):
        grid.lines[ll].monitor_loading = True

    nc = compile_numerical_circuit_at(grid)
    nbus = nc.nbus

    admittances = nc.get_admittance_matrices()
    Vm = np.random.rand(nbus)
    V = Vm + 1j * np.random.rand(nbus)

    Vmat = diags(V)
    Ibus = admittances.Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))
    vm_inv = diags(1 / Vm)
    indptr = admittances.Ybus.indptr
    cols, indices = admittances.Ybus.nonzero()
    diag_ids = np.zeros(nbus, dtype=int)
    for i in range(nbus):
        diag_ids[i] = np.where(indices[indptr[i]:indptr[i + 1]] == i)[0] + indptr[i]

    for i in range(tries):
        for j in range(iter):
        # Old operation
            t_1s = timeit.default_timer()
            # Vmat = diags(V)
            # IbusCJmat = diags(np.conj(Ibus))
            # vm_inv = diags(1 / Vm)
            Vva = 1j * Vmat
            GSvm1 = Vmat @ (IbusCJmat + np.conj(admittances.Ybus @ Vmat)) @ vm_inv  # N x N matrix
            GSva1 = Vva @ (IbusCJmat - np.conj(admittances.Ybus @ Vmat))
            t_1e = timeit.default_timer()
            t1 += t_1e - t_1s

            ###################
           # New operation
            Ybus_V = admittances.Ybus.data * V[admittances.Ybus.indices]

            t_2s = timeit.default_timer()
            data = Ybus_V.copy()
            np.add.at(data, diag_ids, Ibus)
            GSvm2 = csc_matrix((np.conj(data) * (1 / Vm)[indices] * V[cols], indices, indptr),
                         shape=(nbus, nbus)).transpose()
            data = - Ybus_V.copy()
            np.add.at(data, diag_ids, Ibus)
            GSva2 = csc_matrix((np.conj(data) * 1j * V[cols], indices, indptr),
                              shape=(nbus, nbus)).transpose()

            t_2e = timeit.default_timer()

            t2 += t_2e - t_2s
            # t_3s = timeit.default_timer()
            # Ybus_V_copy2 = Ybus_V.copy()
            # np.add.at(Ybus_V_copy2, diag_ids, Ibus)
            # t_3e = timeit.default_timer()

            # t3 += t_3e - t_3s
    print(f'{(t1 - t2)  * 1000 / tries} miliseconds faster.')
    # print(f'{(t2 - t3)  * 1000 / tries} miliseconds faster.')




if __name__ == '__main__':
    pass
    # test_average_speed_1()
    # test_average_speed_2()
    # test_average_speed_3()
    # test_average_speed_4()