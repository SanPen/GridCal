
import numpy as np


def thevenin_funcX2(U, X):
    n = len(U)
    r_3 = np. zeros(n, dtype=complex)
    r_2 = np. zeros(n, dtype=complex)
    r_1 = np. zeros(n, dtype=complex)
    r_0 = np. zeros(n, dtype=complex)
    T_03 = np. zeros(n, dtype=complex)
    T_02 = np. zeros(n, dtype=complex)
    T_01 = np. zeros(n, dtype=complex)
    T_00 = np. zeros(n, dtype=complex)
    T_13 = np. zeros(n, dtype=complex)
    T_12 = np. zeros(n, dtype=complex)
    T_11 = np. zeros(n, dtype=complex)
    T_10 = np. zeros(n, dtype=complex)
    T_23 = np. zeros(n, dtype=complex)
    T_22 = np. zeros(n, dtype=complex)
    T_21 = np. zeros(n, dtype=complex)
    T_20 = np. zeros(n, dtype=complex)

    r_0[0] = -1
    r_1[0:n-1] = U[1:n]
    r_2[0:n-2] = U[2:n] - U[1] * X[1:n-1]

    T_00[0] = -1
    T_01[0] = -1
    T_02[0] = -1
    T_10[0] = 0
    T_11[0] = 1
    T_12[0] = 1
    T_20[0] = 0
    T_21[0] = 0
    T_22[0] = -U[1]

    for l in range(n):  # ANAR CALCULANT CONSTANTS , RESIDUS I POLINOMIS
        a = (r_2[0] * r_1[0]) / (- r_0[1] * r_1[0] + r_0[0] * r_1[1] - r_0[0] * r_2[0])
        b = -a * r_0[0] / r_1[0]
        c = 1 - b
        T_03[0] = b * T_01[0] + c * T_02[0]
        T_03[1:n] = a * T_00[0:n-1] + b * T_01[1:n] + c * T_02[1:n]
        T_13[0] = b * T_11[0] + c * T_12[0]
        T_13[1:n] = a * T_10[0:n-1] + b * T_11[1:n] + c * T_12[1:n]
        T_23[0] = b * T_21[0] + c * T_22[0]
        T_23[1:n] = a * T_20[0:n-1] + b * T_21[1:n] + c * T_22[1:n]
        r_3[0:n-2] = a * r_0[2:n] + b * r_1[2:n] + c * r_2[1:n-1]

        if l == n - 1:
            t_0 = T_03
            t_1 = T_13
            t_2 = T_23

        r_0[:] = r_1[:]
        r_1[:] = r_2[:]
        r_2[:] = r_3[:]
        T_00[:] = T_01[:]
        T_01[:] = T_02[:]
        T_02[:] = T_03[:]
        T_10[:] = T_11[:]
        T_11[:] = T_12[:]
        T_12[:] = T_13[:]
        T_20[:] = T_21[:]
        T_21[:] = T_22[:]
        T_22[:] = T_23[:]

        r_3 = np.zeros(n, dtype=complex)
        T_03 = np.zeros(n, dtype=complex)
        T_13 = np.zeros(n, dtype=complex)
        T_23 = np.zeros(n, dtype=complex)

    usw = -sum(t_0) / sum(t_1)
    sth = -sum(t_2) / sum(t_1)

    sigma_bo = sth / (usw * np.conj(usw))

    u = 0.5 + np.sqrt(0.25 + np.real(sigma_bo) - np. imag(sigma_bo)**2) + np.imag(sigma_bo)*1j  # positive branch
    #u = 0.5 - np.sqrt(0.25 + np.real(sigma_bo) - np.imag(sigma_bo) ** 2) + np.imag(sigma_bo) * 1j  # negative branch
    ufinal = u*usw

    return ufinal


def thevenin4all(U, X):
    """

    :param U:
    :param X:
    :return:
    """
    n_coeff, nbus = U.shape
    r_3 = np. zeros((n_coeff, nbus), dtype=complex)
    r_2 = np. zeros((n_coeff, nbus), dtype=complex)
    r_1 = np. zeros((n_coeff, nbus), dtype=complex)
    r_0 = np. zeros((n_coeff, nbus), dtype=complex)
    T_03 = np. zeros((n_coeff, nbus), dtype=complex)
    T_02 = np. zeros((n_coeff, nbus), dtype=complex)
    T_01 = np. zeros((n_coeff, nbus), dtype=complex)
    T_00 = np. zeros((n_coeff, nbus), dtype=complex)
    T_13 = np. zeros((n_coeff, nbus), dtype=complex)
    T_12 = np. zeros((n_coeff, nbus), dtype=complex)
    T_11 = np. zeros((n_coeff, nbus), dtype=complex)
    T_10 = np. zeros((n_coeff, nbus), dtype=complex)
    T_23 = np. zeros((n_coeff, nbus), dtype=complex)
    T_22 = np. zeros((n_coeff, nbus), dtype=complex)
    T_21 = np. zeros((n_coeff, nbus), dtype=complex)
    T_20 = np. zeros((n_coeff, nbus), dtype=complex)

    r_0[0, :] = -1.0
    r_1[0:n_coeff-1, :] = U[1:n_coeff, :]
    r_2[0:n_coeff-2, :] = U[2:n_coeff, :] - U[1, :] * X[1:n_coeff-1, :]

    T_00[0, :] = -1.0
    T_01[0, :] = -1.0
    T_02[0, :] = -1.0
    T_10[0, :] = 0.0
    T_11[0, :] = 1.0
    T_12[0, :] = 1.0
    T_20[0, :] = 0.0
    T_21[0, :] = 0.0
    T_22[0, :] = -U[1, :]

    for l in range(n_coeff):  # ANAR CALCULANT CONSTANTS , RESIDUS I POLINOMIS

        a = (r_2[0, :] * r_1[0, :]) / (- r_0[1, :] * r_1[0, :] + r_0[0, :] * r_1[1, :] - r_0[0, :] * r_2[0, :])
        b = -a * r_0[0, :] / r_1[0, :]
        c = 1.0 - b
        T_03[0, :] = b * T_01[0, :] + c * T_02[0, :]
        T_03[1:n_coeff, :] = a * T_00[0:n_coeff-1, :] + b * T_01[1:n_coeff, :] + c * T_02[1:n_coeff, :]
        T_13[0, :] = b * T_11[0, :] + c * T_12[0, :]
        T_13[1:n_coeff, :] = a * T_10[0:n_coeff-1, :] + b * T_11[1:n_coeff, :] + c * T_12[1:n_coeff, :]
        T_23[0, :] = b * T_21[0, :] + c * T_22[0, :]
        T_23[1:n_coeff, :] = a * T_20[0:n_coeff-1, :] + b * T_21[1:n_coeff, :] + c * T_22[1:n_coeff, :]
        r_3[0:n_coeff-2, :] = a * r_0[2:n_coeff, :] + b * r_1[2:n_coeff, :] + c * r_2[1:n_coeff-1, :]

        if l == n_coeff - 1:
            t_0 = T_03
            t_1 = T_13
            t_2 = T_23

        r_0 = r_1
        r_1 = r_2
        r_2 = r_3
        T_00 = T_01
        T_01 = T_02
        T_02 = T_03
        T_10 = T_11
        T_11 = T_12
        T_12 = T_13
        T_20 = T_21
        T_21 = T_22
        T_22 = T_23

        r_3 = np.zeros((n_coeff, nbus), dtype=complex)
        T_03 = np.zeros((n_coeff, nbus), dtype=complex)
        T_13 = np.zeros((n_coeff, nbus), dtype=complex)
        T_23 = np.zeros((n_coeff, nbus), dtype=complex)

    usw = -t_0.sum(axis=0) / t_1.sum(axis=0)
    sth = -t_2.sum(axis=0) / t_1.sum(axis=0)

    sigma_bo = sth / (usw * np.conj(usw))

    u = 0.5 + np.sqrt(0.25 + np.real(sigma_bo) - np. imag(sigma_bo)**2) + np.imag(sigma_bo) * 1j  # positive branch
    # u = 0.5 - np.sqrt(0.25 + np.real(sigma_bo) - np.imag(sigma_bo) ** 2) + np.imag(sigma_bo) * 1j  # negative branch
    ufinal = u * usw

    return ufinal


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    from GridCal.Engine.Simulations.PowerFlow.helm_power_flow import helm_coefficients_josep, pade4all
    import pandas as pd

    np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    grid = FileOpen(fname).open()

    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    U_, X_, Q_, iter_ = helm_coefficients_josep(Yseries=inputs.Yseries,
                                                V0=inputs.Vbus,
                                                S0=inputs.Sbus,
                                                Ysh0=inputs.Ysh,
                                                pq=inputs.pq,
                                                pv=inputs.pv,
                                                sl=inputs.ref,
                                                pqpv=inputs.pqpv,
                                                tolerance=1e-6,
                                                max_coeff=10,
                                                verbose=False)

    # get the voltages with the thevenin approximant
    thevenin_voltage = thevenin4all(U=U_, X=X_)
    pade_voltage = pade4all(order=U_.shape[0]-1, coeff_mat=U_, s=1)

    # check the implementation of thevenin4all
    n = U_.shape[1]
    for i in range(n):
        vsel = thevenin_funcX2(U=U_[:, i], X=X_[:, i])
        assert np.isclose(thevenin_voltage[i], vsel)

    data = np.c_[np.abs(U_.sum(axis=0)), np.abs(pade_voltage), np.abs(thevenin_voltage)]
    df = pd.DataFrame(data=data, columns=['Sum', 'Padè', 'Thevenin'])
    print(df)