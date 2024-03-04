import numpy as np
import matplotlib.pyplot as plt
from trunk.investments.InvestmentsEvaluation.MVRSM import MVRSM_normalization_minimize


def schaffer_n2(x):
    # Discontinuous Schaffer function with 2 objectives

    if x[0] <= 1:
        f1 = -x[0]
    elif 1 < x[0] <= 3:
        f1 = x[0] - 2
    elif 3 < x[0] <= 4:
        f1 = 4 - x[0]
    else:
        f1 = x[0] - 4

    f2 = (x[0] - 5)**2

    return np.array([f1, f2], dtype=float)


def kursawe(x):
    # Discontinuous Kursawe function with 2 objectives

    f1 = 0.0
    f2 = 0.0

    for i in range(2):
        f1 += -10 * np.exp(-0.2 * np.sqrt(x[i]**2 + x[i+1]**2))

    for i in range(3):
        f2 += abs(x[i])**0.8 + 5 * np.sin(x[i]**3)

    return np.array([f1, f2], dtype=float)


def call_schaffer_n2():
    max_evals = 500
    rand_evals = 100
    size = 1

    x0 = np.random.uniform(low=-5.0, high=10.0, size=size)
    lb = np.array([-5.0])
    ub = np.array([10.0])

    f_obj = schaffer_n2

    y_sorted, x_sorted, y_pop, x_pop = MVRSM_normalization_minimize(obj_func=f_obj,
                                                                    x0=x0,
                                                                    lb=lb,
                                                                    ub=ub,
                                                                    num_int=0,
                                                                    max_evals=max_evals,
                                                                    rand_evals=rand_evals,
                                                                    n_objectives=2)

    return y_sorted, x_sorted, y_pop, x_pop, rand_evals


def call_kursawe():
    max_evals = 1000
    rand_evals = 200
    size = 3

    x0 = np.random.uniform(low=-5.0, high=5.0, size=size)
    lb = np.array([-5.0] * size)
    ub = np.array([5.0] * size)

    f_obj = kursawe

    y_sorted, x_sorted, y_pop, x_pop = MVRSM_normalization_minimize(obj_func=f_obj,
                                                                    x0=x0,
                                                                    lb=lb,
                                                                    ub=ub,
                                                                    num_int=0,
                                                                    max_evals=max_evals,
                                                                    rand_evals=rand_evals,
                                                                    n_objectives=2)

    return y_sorted, x_sorted, y_pop, x_pop, rand_evals


if __name__ == "__main__":

    # y_sorted, x_sorted, y_pop, x_pop, rand_eval = call_schaffer_n2()
    y_sorted, x_sorted, y_pop, x_pop, rand_eval = call_kursawe()

    plt.scatter(y_sorted[:, 0], y_sorted[:, 1], s=6, c='g')
    # plt.scatter(y_pop[rand_eval:, 0], y_pop[rand_eval:, 1], s=6, c='b')
    # plt.scatter(y_pop[:rand_eval, 0], y_pop[:rand_eval, 1], s=6, c='r')
    plt.show()
    print()
