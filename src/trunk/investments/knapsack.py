import numpy as np
import matplotlib.pyplot as plt
from trunk.investments.InvestmentsEvaluation.MVRSM import MVRSM_normalization_minimize, MVRSM_minimize
from trunk.MVRSM.MVRSM_mo import MVRSM_multi_minimize


def knapsack_10(x):
    # Knapsack problem of size 10
    w = np.array([2, 3, 5, 7, 1, 4, 1, 2, 8, 1])
    v = np.array([10, 5, 15, 7, 6, 18, 3, 12, 17, 4])
    w_lim = 15

    fo = - np.dot(v, x)  # invert sign to minimize
    fc = np.dot(w, x)

    if fc > w_lim:
        return fo + (fc - w_lim) * 10
    else:
        return fo


if __name__ == "__main__":
    max_evals = 200
    rand_evals = 20
    size = 10

    x0 = np.random.randint(2, size=size)
    lb = np.zeros(size)
    ub = np.ones(size)

    f_obj = knapsack_10

    y_sorted, x_sorted, y_pop, x_pop = MVRSM_normalization_minimize(obj_func=f_obj,
                                                                    x0=x0,
                                                                    lb=lb,
                                                                    ub=ub,
                                                                    num_int=size,
                                                                    max_evals=max_evals,
                                                                    rand_evals=rand_evals)

    plt.scatter(range(max_evals - rand_evals), y_pop[rand_evals:], c=np.arange(max_evals - rand_evals), cmap='viridis',
                s=6, label='All Population')
    plt.scatter(range(rand_evals), y_pop[:rand_evals], s=6, c='r', label='Random iterations')
    plt.legend(loc='upper right', bbox_to_anchor=(1, 1), fontsize='8')

    plt.show()
    print()
