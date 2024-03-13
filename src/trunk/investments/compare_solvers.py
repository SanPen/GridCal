import numpy as np
import matplotlib.pyplot as plt
from trunk.investments.InvestmentsEvaluation.MVRSM import MVRSM_normalization_minimize
from trunk.MVRSM.MVRSM_mo import MVRSM_multi_minimize


def schaffer_n2(x):
    x = x[0]
    if x <= 1:
        obj1 = -x
    elif x <= 3:
        obj1 = x - 2
    elif x <= 4:
        obj1 = 4 - x
    else:
        obj1 = x - 4

    obj2 = (x - 5) ** 2

    return np.array([obj1, obj2], dtype=float)


def zdt3(x):
    # Objective function 1
    f1 = x[0]

    # G function for constraint handling
    g = 1 + 9 / 29 * np.sum(x[1:])

    # H function for constraint handling
    h = 1 - np.sqrt(f1 / g) - (f1 / g) * np.sin(10 * np.pi * f1)

    # Objective function 2
    f2 = g * h

    return np.array([f1, f2], dtype=float)


def plot_everything(y, initial_value, pareto, random_evals, title, figure_num):
    plt.figure(figure_num)
    plt.scatter(y[random_evals:, 0], y[random_evals:, 1],
                c=np.arange(len(y[random_evals:])),
                cmap='viridis', s=6, label='All Population')  # plot from rand_evals to max_evals

    plt.scatter(y[:random_evals, 0], y[:random_evals, 1], s=6, c='r', label='Random iterations')
    plt.scatter(pareto[:, 0], pareto[:, 1], s=3, c='g', label='Pareto')
    plt.scatter(initial_value[0], initial_value[1], s=10, marker='*', label='Initial point')

    plt.title(title)
    plt.xlabel('f1')
    plt.ylabel('f2')

    plt.xlim((0, 1))
    plt.ylim((-1, 6))

    plt.legend(loc='upper right', bbox_to_anchor=(1, 1), fontsize='8')

    # common_indices = np.isin(y_sorted_[:, 0], y_population_[:rand_evals, 0])
    # common_elements = y_sorted_[common_indices]
    # plt.scatter(common_elements[:, 0], common_elements[:, 1], s=6, c='r', label='Random iterations')


def plot_iterations(x_multi, x_single, figure_num, title, ylabel):
    plt.figure(figure_num)
    plt.plot(np.arange(len(x_multi)), x_multi, c='b', label='Multi-objective')
    plt.plot(np.arange(len(x_single)), x_single, c='r', label='Single-objective')

    plt.title(title)
    plt.xlabel('Iterations')
    plt.ylabel(ylabel)
    plt.legend()


if __name__ == "__main__":

    rand_evals = 100

    # ZDT-N3 test function
    x0 = np.zeros(30)
    lb = np.zeros(30)
    ub = np.ones(30)
    f_obj = zdt3

    values0 = []
    for i in range(0, 100, 1):
        x = i / 100
        x0[0] = x
        result = zdt3(x0)
        values0.append(result)

    x0 = np.ones(30) * 0.5
    y0 = zdt3(x0)
    print(y0)
    # print(x0)
    values0 = np.array(values0)


    '''
    # Schaffer test function
    x0 = np.array([0.])
    lb = np.array([-5.])
    ub = np.array([10])
    f_obj = schaffer_n2
    '''

    y_sorted_, x_sorted_, y_population_, x_population_ = MVRSM_multi_minimize(obj_func=f_obj,
                                                                              x0=x0,
                                                                              lb=lb,
                                                                              ub=ub,
                                                                              num_int=0,
                                                                              max_evals=3000,
                                                                              n_objectives=2,
                                                                              rand_evals=rand_evals)

    y_sorted_2, x_sorted_2, y_population_2, x_population_2 = MVRSM_normalization_minimize(obj_func=f_obj,
                                                                                          x0=x0,
                                                                                          lb=lb,
                                                                                          ub=ub,
                                                                                          num_int=0,
                                                                                          max_evals=3000,
                                                                                          rand_evals=rand_evals,
                                                                                          n_objectives=2)

    ax_lim = True
    plot_everything(y=y_population_,
                    initial_value=y0,
                    pareto=values0,
                    random_evals=rand_evals,
                    figure_num=1,
                    title='Multi-objective')

    plot_everything(y=y_population_2,
                    initial_value=y0,
                    pareto=values0,
                    random_evals=rand_evals,
                    figure_num=2,
                    title='Single-objective')

    plot_iterations(x_population_[:, 0],
                    x_population_2[:, 0],
                    figure_num=3,
                    title='First x value',
                    ylabel='x[0]')

    plot_iterations(np.sum(x_population_[:, 1:], axis=1),
                    np.sum(x_population_2[:, 1:], axis=1),
                    figure_num=4,
                    title='Summation',
                    ylabel='np.sum(x[1:])')

    plt.show()
