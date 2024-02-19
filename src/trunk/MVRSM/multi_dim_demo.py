
import numpy as np
from MVRSM import MVRSM_multi_minimize


# Define the Ackley function
def ackley(x, a=20, b=0.2, c=2*np.pi):
    d = len(x)  # Dimension of the input vector
    sum_sq_term = -a * np.exp(-b * np.sqrt(sum(x**2) / d))
    cos_term = -np.exp(sum(np.cos(c * x) / d))
    return sum_sq_term + cos_term + a + np.exp(1)


def func(x):
    """
    An objective function with different outputs
    :param x: n-dimensinal values
    :return: 3-dim output
    """
    f = ackley(x)

    return np.array([f, np.sqrt(f), 1000.0 * np.sin(f)])


d = 10  # Total number of variables
lb = -2 * np.ones(d).astype(int)  # Lower bound
ub = 2 * np.ones(d).astype(int)  # Upper bound
num_int = 3  # number of integer variables
lb[0:num_int] = 0
ub[0:num_int] = num_int + 1

x0 = np.zeros(d)  # Initial guess

# Random initial guess (integer)
x0[0:num_int] = np.round(np.random.rand(num_int) * (ub[0:num_int] - lb[0:num_int]) + lb[0:num_int])

# Random initial guess (continuous)
x0[num_int:d] = np.random.rand(d - num_int) * (ub[num_int:d] - lb[num_int:d]) + lb[num_int:d]

x_best, y_best, model = MVRSM_multi_minimize(obj_func=func,
                                             x0=x0,
                                             lb=lb,
                                             ub=ub,
                                             num_int=num_int,
                                             max_evals=200,
                                             n_objectives=3,
                                             rand_evals=50,
                                             args=())

print("best")
print(y_best)
