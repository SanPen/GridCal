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


if __name__ == "__main__":

    x0 = np.ones(30) * 0.3
    lb = np.zeros(30)
    ub = np.ones(30)
    f_obj = zdt3
    ax_lim = True

    '''x0 = np.array([0.])
    lb = np.array([-5.])
    ub = np.array([10])
    f_obj = schaffer_n2
    ax_lim = False'''

    y_sorted_, x_sorted_, y_population_, x_population_ = MVRSM_multi_minimize(obj_func=f_obj,
                                                                              x0=x0,
                                                                              lb=lb,
                                                                              ub=ub,
                                                                              num_int=0,
                                                                              max_evals=500,
                                                                              n_objectives=2,
                                                                              rand_evals=50)

    y_sorted_2, x_sorted_2, y_population_2, x_population_2 = MVRSM_normalization_minimize(obj_func=f_obj,
                                                                                          x0=x0,
                                                                                          lb=lb,
                                                                                          ub=ub,
                                                                                          num_int=0,
                                                                                          max_evals=500,
                                                                                          rand_evals=50,
                                                                                          n_objectives=2)

    '''# Assuming y_population_ is your data
    pareto_points = identify_pareto(y_population_)

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')

    px, py, pz = zip(*pareto_points)
    ax.set_xlabel('f1')
    ax.set_ylabel('f2')
    ax.set_zlabel('f3')

    ax.scatter(px, py, pz, c='r', marker='^', label='Pareto Front')

    plt.show()'''

    # Figure 1
    plt.figure(1)
    plt.scatter(y_population_[:, 0], y_population_[:, 1], s=6, label='All Population')
    plt.scatter(y_population_[:50, 0], y_population_[:50, 1], s=6, c='r', label='Random iterations')
    plt.title('Multi-objective')
    plt.xlabel('f1')
    plt.ylabel('f2')
    if ax_lim:
        plt.xlim((0, 1))
        plt.ylim((-1, 6))
    plt.legend()  # Add legend to distinguish between All Population and Selected Subset

    # Figure 2
    plt.figure(2)
    plt.scatter(y_population_2[:, 0], y_population_2[:, 1], s=6, label='All Population')
    plt.scatter(y_population_2[:50, 0], y_population_2[:50, 1], s=6, c='r', label='Random iterations')
    plt.title('Single-objective w normalization')
    plt.xlabel('f1')
    plt.ylabel('f2')
    if ax_lim:
        plt.xlim((0, 1))
        plt.ylim((-1, 6))
    plt.legend()  # Add legend to distinguish between All Population and Selected Subset

    plt.show()

    '''# Create a figure and axis object
    fig, ax1 = plt.subplots()

    # Plotting the values on the left y-axis
    ax1.plot(range(len(y_population_)), y_population_[:, 0], label='f1', color='blue')
    ax1.set_xlabel('Iteration')
    ax1.tick_params('y', colors='blue')

    # Create a twin axis on the right side
    ax2 = ax1.twinx()

    # Plotting the values on the right y-axis
    ax2.plot(range(len(y_population_)), y_population_[:, 1], label='f2', color='red')
    ax2.tick_params('y', colors='red')

    # Plotting the values on the right y-axis
    ax2.plot(range(len(all_crits)), all_crits[:, 1], label='f2 single', color='orange')

    # Plotting the values on the right y-axis
    ax1.plot(range(len(all_crits)), all_crits[:, 0], label='f1 single', color='green')


    # Adding legend
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left')



    # Showing the plot
    plt.show()'''
