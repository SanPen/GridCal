# IDONE uses a piece-wise linear surrogate model for optimization of
# expensive cost functions with integer variables.
#
# IDONE_minimize(obj, x0, lb, ub, max_evals) solves the minimization problem
#
# min f(x)
# st. lb<=x<=ub, x is integer
#
# where obj is the objective function, x0 the initial guess,
# lb and ub are the bounds (assumed integer), 
# and max_evals is the maximum number of objective evaluations.

# from: https://bitbucket.org/lbliek2/idone/src/master/

import os
import math
import random
import time
import numpy as np
import scipy.optimize as opt


class ModelData:

	def __init__(self, W, B, D, c, P, reg):
		"""
		Data structure for the model
		:param W: Basis function weights
		:param B: Basis function bias
		:param D: Number of basis functions
		:param c: Model weights, to be trained with recursive least squares (RLS)
		:param P: RLS covariance matrix
		:param reg: Regularization parameter. 1e-8 is good for the noiseless case, change to something like 1e-3 if there is noise.
		"""
		self.W = W
		self.B = B
		self.D = D
		self.c = c
		self.P = P
		self.reg = reg

	def update(self, x, y):
		"""
		Update the model when a new data point (x,y) comes in
		:param x:
		:param y:
		:return:
		"""
		Zx = Z(x, self.W, self.B)

		# Recursive least squares algorithm
		temp = np.matmul(self.P, Zx)
		g = temp / (1 + np.matmul(np.transpose(Zx), temp))
		self.P = self.P - np.matmul(g, np.transpose(temp))

		# Only here, output y is used (to update the model weights)
		self.c = self.c + (y - np.matmul(np.transpose(Zx), self.c)) * g


def ReLU(x):
	"""
	Rectified Linear Unit
	:param x:
	:return:
	"""
	return np.maximum(0, x)


def ReLUderiv(x):
	"""
	Derivative of Rectified Linear Unit
	:param x:
	:return:
	"""
	return (x > 0) + 0.5 * (x == 0)


def Z(x, W, B):
	"""
	Transform input into model basis functions Z=ReLU(W*x+B)
	:param x: solution candidate
	:param W: Basis function weights
	:param B: Basis function bias
	:return:
	"""
	x = np.asarray(x)
	x = x.reshape(-1, 1)
	temp = np.matmul(W, x)
	temp = temp + B
	temp = np.asarray(temp)
	Zx = ReLU(temp)
	return Zx


def Zderiv(x, W, B):
	"""
	Derivative of basis functions w.r.t. x
	:param x: solution candidate
	:param W: Basis function weights
	:param B: Basis function bias
	:return:
	"""
	x = np.asarray(x)
	x = x.reshape(-1, 1)
	temp = np.matmul(W, x)
	temp = temp + B
	temp = np.asarray(temp)
	dZx = ReLUderiv(temp)
	return dZx


def initialize_model(x0, d, lb, ub, reg=1e-8):
	"""
	Initialize the surrogate model
	:param x0: initial guess
	:param d: number of dimensions
	:param lb: lower bounds
	:param ub: upper bounds
	:param reg: Regularization parameter.
				1e-8 is good for the noiseless case, change to something like 1e-3 if there is noise.
	:return:
	- next_X: candidate solution presented by the algorithm
	- model: updated model
	"""

	next_X = np.copy(x0)

	# Define basis functions Z=ReLU(W*x+B)
	W = []  # Basis function weights
	B = []  # Basis function bias

	# Add a constant basis function independent on the variable x, giving the model an offset
	W.append([0] * d)
	B.append([1])

	# Add basis functions dependent on one variable
	for k in range(d):
		for i in range(lb[k], ub[k] + 1):
			if i == lb[k]:
				temp = [0] * d
				temp[k] = 1
				W.append(np.copy(temp))
				B.append([-i])
			elif i == ub[k]:
				temp = [0] * d
				temp[k] = -1
				W.append(np.copy(temp))
				B.append([i])
			else:
				temp = [0] * d
				temp[k] = -1
				W.append(np.copy(temp))
				B.append([i])
				temp = [0] * d
				temp[k] = 1
				W.append(np.copy(temp))
				B.append([-i])

	# Add basis functions dependent on two subsequent variables: remove for basic IDONE
	for k in range(1, d):
		for i in range(lb[k] - ub[k - 1], ub[k] - lb[k - 1] + 1):
			if i == lb[k] - ub[k - 1]:
				temp = [0] * d
				temp[k] = 1
				temp[k - 1] = -1
				W.append(np.copy(temp))
				B.append([-i])
			elif i == ub[k] - lb[k - 1]:
				temp = [0] * d
				temp[k] = -1
				temp[k - 1] = 1
				W.append(np.copy(temp))
				B.append([i])
			else:
				temp = [0] * d
				temp[k] = -1
				temp[k - 1] = 1
				W.append(np.copy(temp))
				B.append([i])
				temp = [0] * d
				temp[k] = 1
				temp[k - 1] = -1
				W.append(np.copy(temp))
				B.append([-i])

	W = np.asarray(W)
	B = np.asarray(B)

	D = len(B)  # Number of basis functions
	c = np.ones((D, 1))  # Model weights, to be trained with recursive least squares (RLS)
	c[0] = 0  # Start out with no model offset

	P = np.diag(np.ones(D)) / reg  # RLS covariance matrix

	model = ModelData(W, B, D, c, P, reg)

	return next_X, model


def f_out(x2, model: ModelData):
	"""
	Define model output for any new input x2
	:param x2:
	:param model:
	:return:
	"""
	return np.matmul(np.transpose(model.c), Z(x2, model.W, model.B)).item(0, 0)


def f_out_derivative(x2, model: ModelData):
	"""
	Define model output derivative for any new input x2 (used in the optimization step)
	:param x2:
	:param model:
	:return:
	"""
	c = np.transpose(model.c)
	temp = np.reshape(Zderiv(x2, model.W, model.B), (Zderiv(x2, model.W, model.B)).shape[0])
	temp = np.matmul(np.diag(temp), model.W)
	result = np.transpose(np.matmul(c, temp))
	return result


def scale(y, y0=None):
	# Uncomment to add a scaling factor
	# if abs(y0)>1e-8:
	# y = (y-y0)/abs(y0)
	# else:
	# y = (y-y0)
	return y


def inv_scale(y, y0=None):
	# if abs(y0)>1e-8:
	# y = y*abs(y0)+y0
	# else:
	# y = y+y0
	return y


def minimize(f_obj, x0, lb, ub, max_eval, reg=1e-8):
	"""
	IDONE minimize function 
	:param f_obj: Objective function
	:param x0: Initial guess
	:param lb: Variables' lower bound
	:param ub: Variables' upper bound
	:param max_eval: maximum number of evaluations
	:param reg: Regularization parameter. 
				1e-8 is good for the noiseless case, change to something like 1e-3 if there is noise.
	:return:
	- best_X
	- inv_scale(best_y, None)
	- model_data
	- log filename
	"""
	current_time = time.time()  # time when starting the algorithm
	filename = 'log_IDONE_' + str(current_time) + ".log"

	d = len(x0)  # dimension, number of variables

	# Start actual algorithm
	next_X, model_data = initialize_model(x0, d, lb, ub, reg)
	best_X = np.copy(next_X)  # Best candidate solution found so far
	best_y = 9999999  # Best objective function value found so far
	
	# Iteratively evaluate the objective, update the model, find the minimum of the model, and explore the search space
	for ii in range(max_eval):

		print(f"Starting IDONE iteration {ii}/{max_eval}")

		x = np.copy(next_X).astype(int)

		if ii == 0:
			y = f_obj(x)  # Evaluate the objective
			
			# Scale with respect to initial y value, causing the optimum to lie below 0.
			# This is better for exploitation and prevents the algorithm from getting stuck at the boundary.
			y0 = y
					
			y = scale(y, y0)
		else:
			y = scale(f_obj(x), 0)  # Evaluate the objective and scale it

		# Keep track of the best found objective value and candidate solution so far
		if y < best_y:
			best_X = np.copy(x)
			best_y = y

		# Update the surrogate model
		time_start = time.time() 
		model_data.update(x, y)
		update_time = time.time()-time_start  # Time used to update the model
		
		# Minimization of the surrogate model
		time_start = time.time()
		temp = opt.minimize(fun=f_out,
							x0=x,
							args=(model_data,),
							method='L-BFGS-B',
							bounds=opt.Bounds(lb, ub),
							jac=f_out_derivative,
							options={'maxiter': 20, 'maxfun': 20})

		minimization_time = time.time()-time_start  # Time used to find the minimum of the model
		next_X = np.copy(temp.x)
		next_X = np.round(next_X)  # Round to nearest integer point
		next_X = [int(x) for x in next_X]

		# Just to be sure, clip to the bounds
		np.clip(next_X, lb, ub)
		
		# Check if minimizer really gives better result
		if f_out(next_X, model_data) > f_out(x, model_data) + 1e-8:
			print('Warning: minimization of the surrogate model in IDONE yielded a worse solution, maybe something went wrong.')
		
		# Exploration step (else the algorithm gets stuck in the local minimum of the surrogate model)
		next_X_before_exploration = np.copy(next_X)
		next_X = np.copy(next_X)

		# Skip exploration before the last iteration, to end at the exact minimum of the surrogate model.
		if ii < max_eval-2:
			for j in range(d):
				r = random.random()
				a = next_X[j]
				prob = 1.0 / d  # Probability for each variable to increase or decrease
				if r < prob:
					if a == lb[j] and a < ub[j]:
						a += 1  # Explore to the right

					elif a == ub[j] and a > lb[j]:
						a -= 1  # Explore to the left

					elif lb[j] < a < ub[j]:
						r2 = random.random()  # Explore left or right
						if r2 < 0.5:
							a += 1
						else:
							a -= 1
				next_X[j] = a
				
		# Just to be sure, clip to the bounds again
		np.clip(next_X, lb, ub)		
		
		# If even after exploration x does not change, go to a completely random x
		# if np.allclose(next_X,x):
		# 	next_X = np.round(np.random.rand(d)*(ub-lb) + lb)
		
		# Save data to log file
		with open(filename, 'a') as f:
			print('\n\n IDONE iteration: ', ii, file=f)
			print('Time spent training the model:				 ', update_time, file=f)
			print('Time spent finding the minimum of the model: ', minimization_time, file=f)
			print('Current time: ', time.time(), file=f)
			print('Evaluated data point and evaluation:						   ', np.copy(x).astype(int),  ', ',  inv_scale(y), file=f)
			print('Best found data point and evaluation so far:				   ', np.copy(best_X).astype(int),  ', ',  inv_scale(best_y), file=f)
			print('Best data point according to the model and predicted value:    ', next_X_before_exploration, ', ', inv_scale(f_out(next_X_before_exploration, model_data)), file=f)
			print('Suggested next data point and predicted value:			       ', next_X,   ', ', inv_scale(f_out(next_X, model_data)), file=f)
			if ii >= max_eval-1:
				print('Model parameters: ', np.transpose(model_data.c), file=f)
	
	return best_X, inv_scale(best_y, None), model_data, filename


def read_log(filename):
	"""
	Read data from log file (this reads the best found objective values at each iteration)
	:param filename:
	:return:
	"""
	with open(filename, 'r') as f:
			IDONEfile = f.readlines()
			IDONE_best = []
			for i, lines in enumerate(IDONEfile):
				searchterm = 'Best data point according to the model and predicted value:'
				if searchterm in lines:
					temp = IDONEfile[i-1]
					temp = temp.split('] , ')
					temp = temp[1]
					IDONE_best.append(float(temp))
	return IDONE_best


def plot_results(filename):
	"""
	Plot the best found objective values at each iteration
	:param filename:
	:return:
	"""
	import matplotlib.pyplot as plt
	IDONE_ev = read_log(filename)
	plt.plot(IDONE_ev)
	plt.xlabel('Iteration')
	plt.ylabel('Objective')
	plt.grid()
	plt.show()
