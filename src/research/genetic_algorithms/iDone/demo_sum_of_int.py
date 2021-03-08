import IDONE
import numpy as np
import os


def f(x):
	return -np.sum(x)


def test_sum_of_integers(d, max_eval=100):
	"""
	Maximize the simple summation function
	:param d: number of dimensions
	:param max_eval: maximum number of evaluations
	:return:
	"""
	print(f"Testing IDONE on the {d}-dimensional Rosenbrock function with integer constraints.")
	print("The known global minimum is f(1,1,...,1)=0")
	lb = np.zeros(d, dtype=int)  # Lower bound
	ub = np.ones(d, dtype=int)  # Upper bound
	x0 = np.round(np.random.rand(d) * (ub - lb) + lb)  # Random initial guess

	solX, solY, model, logfile = IDONE.minimize(f, x0, lb, ub, max_eval, args=())
	print("Solution found: ")
	print(f"X = {solX}")
	print(f"Y = {solY}")
	return solX, solY, model, logfile


d = 80  # Change this number to optimize the function for different numbers of variables
max_eval_ = 5 * d
solX_, solY_, model_, logfile_ = test_sum_of_integers(d, max_eval_)

# Visualise the results
IDONE.plot_results(logfile_)
