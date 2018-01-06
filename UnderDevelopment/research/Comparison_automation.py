from matplotlib import pyplot as plt
import numpy as np
plt.ion()



def replace_non_ascii(text):
    return ''.join([i if ord(i) < 128 else ' ' for i in text])


def plot_full_convergence(err, powerInjections, S, title, ext='.eps', save=True):
    plt.figure()

    titles = ['Maximum mismatch', 'PV nodes P mismatch', 'PV nodes Q mismatch', 'PQ nodes P mismatch', 'PQ nodes Q mismatch']
    idx = [0, 1, 3, 4]
    k = 0
    for i in idx:
        k += 1
        plt.subplot(2, 2, k)
        if not np.all(err[i] == 0):
            plt.plot(err[i])
            plt.title(titles[i])
            try:
                plt.yscale('log')
            except:
                print()

    fig = plt.gcf()
    fig.suptitle(title, fontsize=14)

    if save:
        plt.savefig(replace_non_ascii(title).replace(" ", "_") + ext)
    else:
        plt.show()


def plot_errors(err1, err2, title1, title2, title, ext = '.eps', save=True):
    plt.figure()
    plt.plot(err1[0], marker='x', label=title1)
    plt.plot(err2[0], marker='x', label=title2)
    plt.yscale('log')
    plt.ylabel('Error')
    plt.xlabel('Iterations')
    plt.title(title)
    plt.legend()
    if save:
        plt.savefig(replace_non_ascii(title).replace(" ", "_") + ext)
    else:
        plt.show()


def plot_error(err1, title1, title, ext = '.eps', save=True):
    plt.figure()
    plt.plot(err1[0], marker='x', label=title1)
    plt.yscale('log')
    plt.ylabel('Error')
    plt.xlabel('Iterations')
    plt.title(title)
    plt.legend()
    if save:
        plt.savefig(replace_non_ascii(title).replace(" ", "_") + ext)
    else:
        plt.show()


def plot_voltages(Vlst, title, C=None, ext = '.eps', save=True):

    if C is None:
        a = 1
        b = 2
    else:
        a = 2
        b = 2
    V = np.array(Vlst)
    Vm = np.abs(V)
    Va = np.angle(V, deg=True)
    plt.figure(figsize=(9, 5))
    plt.subplot(a, b, 1)
    plt.plot(Vm, label='Module')
    plt.ylabel('Voltage module')
    plt.xlabel('Iterations')

    plt.subplot(a, b, 2)
    plt.plot(Va, label='Angle in degrees')
    plt.ylabel('Voltage angle (degrees)')
    plt.xlabel('Iterations')

    if C is not None:
        n = len(C)
        plt.subplot(a, b, 3)
        # print(n)
        for i in range(n):
            # print(i)
            # print((C[i, :]))
            plt.plot(np.abs(C[i, :]))
        plt.ylabel('Voltage coefficients ')
        plt.xlabel('Iterations')

        plt.subplot(a, b, 4)
        for i in range(n):
            plt.plot(np.angle(C[i, :], deg=True))
        plt.ylabel('Voltage coefficients angle (degrees)')
        plt.xlabel('Iterations')

    fig = plt.gcf()
    fig.suptitle(title)
    if save:
        plt.savefig(replace_non_ascii(title).replace(" ", "_") + ext)
    else:
        plt.show()


if __name__ == "__main__":
    # global vars
    use_sparse = True
    cmax = 40
    usepade = True
    ext = '.eps'

    ########################################################################################################################
    # Pade VS Epsilon
    ########################################################################################################################
    print('Grid load')
    admittances, powerInjections, bustype, \
    voltageSetPoints, slackIndices, nbus, eps = grids.Lynn_example2(use_sparse)
    gridname = '5-node grid'

    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err_pade, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=True)

    V1, C, W, X, R, H, Yred, err_eps, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=False)

    plot_errors(err_pade, err_eps, 'Padè', "Wynn's epsilon", 'Padè VS Epsilon algorithm', ext)

    ########################################################################################################################
    # Lynn 2
    ########################################################################################################################

    print('Grid load')
    admittances, powerInjections, bustype, \
    voltageSetPoints, slackIndices, nbus, eps = grids.Lynn_example2(use_sparse)
    gridname = '5-node grid'

    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=usepade)

    plot_full_convergence(err, powerInjections, S, 'HELM-Z full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)

    # Full convergence characteristics on Lynn 2 (HELM-ASU)
    print('HELM ASU FUll convergence')
    V, Ymat, F, C, W, Q, err, converged, S, Vlst = helm_asu(admittances, slackIndices, cmax, powerInjections,
                                                            voltageSetPoints, bustype, eps, usePade=usepade, useFFT=False)

    try:
        plot_full_convergence(err, powerInjections, S, 'HELM-ASU full convergence characteristic ('+gridname+')', ext)
        plot_voltages(Vlst, 'HELM-ASU voltage convergence ('+gridname+')', ext=ext)
    except:
        print()
    ########################################################################################################################
    # IEEE 5
    ########################################################################################################################

    print('Grid load')
    admittances, B, powerInjections, bustype, voltageSetPoints, slackIndices, nbus, eps = grids.IEEE_5(use_sparse)
    gridname = 'IEEE5'

    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=usepade)

    plot_full_convergence(err, powerInjections, S, 'HELM-Z full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)

    # Full convergence characteristics on Lynn 2 (HELM-ASU)
    print('HELM ASU FUll convergence')
    V, Ymat, F, C, W, Q, err, converged, S, Vlst = helm_asu(admittances, slackIndices, cmax, powerInjections,
                                                            voltageSetPoints, bustype, eps, usePade=usepade, useFFT=False)

    plot_full_convergence(err, powerInjections, S, 'HELM-ASU full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-ASU voltage convergence ('+gridname+')', ext=ext)

    ########################################################################################################################
    # IEEE 14
    ########################################################################################################################
    admittances, B, powerInjections, bustype, voltageSetPoints, slackIndices, nbus, eps = grids.IEEE_14(use_sparse)
    gridname = 'IEEE14'
    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=usepade)

    plot_full_convergence(err, powerInjections, S, 'HELM-Z full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)

    # Full convergence characteristics on Lynn 2 (HELM-ASU)
    print('HELM ASU FUll convergence')
    V, Ymat, F, C, W, Q, err, converged, S, Vlst = helm_asu(admittances, slackIndices, cmax, powerInjections,
                                                            voltageSetPoints, bustype, eps, usePade=usepade, useFFT=False)

    plot_full_convergence(err, powerInjections, S, 'HELM-ASU full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-ASU voltage convergence ('+gridname+')', ext=ext)

    ########################################################################################################################
    # IEEE 30
    ########################################################################################################################
    admittances, B, powerInjections, bustype, voltageSetPoints, slackIndices, nbus, eps = grids.IEEE_30(use_sparse)
    gridname = 'IEEE30'
    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=usepade)

    plot_full_convergence(err, powerInjections, S, 'HELM-Z full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)

    # Full convergence characteristics on Lynn 2 (HELM-ASU)
    print('HELM ASU FUll convergence')
    V, Ymat, F, C, W, Q, err, converged, S, Vlst = helm_asu(admittances, slackIndices, cmax, powerInjections,
                                                            voltageSetPoints, bustype, eps, usePade=usepade, useFFT=False)

    plot_full_convergence(err, powerInjections, S, 'HELM-ASU full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-ASU voltage convergence ('+gridname+')', ext=ext)

    ########################################################################################################################
    # IEEE 118
    ########################################################################################################################
    admittances, B, powerInjections, bustype, voltageSetPoints, slackIndices, nbus, eps = grids.IEEE_118(use_sparse)
    gridname = 'IEEE118'
    # Full convergence characteristics on Lynn 2 (HELM-Z)
    print('HELM Z FUll convergence')
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=usepade)

    plot_full_convergence(err, powerInjections, S, 'HELM-Z full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)

    # Full convergence characteristics on Lynn 2 (HELM-ASU)
    print('HELM ASU FUll convergence')
    V, Ymat, F, C, W, Q, err, converged, S, Vlst = helm_asu(admittances, slackIndices, cmax, powerInjections,
                                                            voltageSetPoints, bustype, eps, usePade=usepade, useFFT=False)

    plot_full_convergence(err, powerInjections, S, 'HELM-ASU full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-ASU voltage convergence ('+gridname+')', ext=ext)

    ########################################################################################################################
    # IEEE 118 (PV pre approximation)
    ########################################################################################################################
    admittances, B, powerInjections, bustype, voltageSetPoints, slackIndices, nbus, eps = grids.IEEE_30(use_sparse)
    gridname = 'IEEE30'

    cmax_red = 15
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices, cmax_red, powerInjections,
                               voltageSetPoints, bustype, eps, usePade=True)

    pv_idx = np.where(bustype == 2)[0]
    Va = np.angle(V1)
    # Va[pv_idx] *= -1
    Vm = np.abs(voltageSetPoints)
    V0 = Vm * np.exp(1j * Va)

    # set the PV to VD
    bustype_ = bustype.copy()
    bustype_[pv_idx] = 3
    slackIndices_ = np.r_[slackIndices, pv_idx]
    slackIndices_.sort()


    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helm_z(admittances, slackIndices_, cmax, powerInjections,
                               V0, bustype_, eps, usePade=True, inherited_pv=pv_idx)


    plot_full_convergence(err, powerInjections, S, 'HELM-Z (PV to Slack) full convergence characteristic ('+gridname+')', ext)
    plot_voltages(Vlst, 'HELM-Z voltage convergence ('+gridname+')', ext=ext)
