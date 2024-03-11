# MVRSM demo
# By Laurens Bliek, 16-03-2020
# Supported functions: 'func2C', 'func3C', 'dim10Rosenbrock',
# 'linearmivabo', 'dim53Rosenbrock', 'dim53Ackley', 'dim238Rosenbrock'
# Example: python demo.py -f dim10Rosenbrock  -n 10 -tl 4
# Here, -f is the function to be optimised, -n is the number of iterations, and -tl is the total number of runs.
# Afterward, use plot_result.py for visualisation.

import sys
# sys.path.append('../bayesopt')
# sys.path.append('../ml_utils')
import argparse
import os
import numpy as np
import pickle
import time
import functions as syntheticFunctions
# from methods.CoCaBO import CoCaBO
# from methods.BatchCoCaBO import BatchCoCaBO
import MVRSM
from hyperopt import fmin, tpe, rand, hp, STATUS_OK, Trials
from functools import partial

from scipy.optimize import rosen
# from linear_MIVABOfunction import Linear


# CoCaBO code taken from:
# -*- coding: utf-8 -*-
# ==========================================
# Title:  run_cocabo_exps.py
# Author: Binxin Ru and Ahsan Alvi
# Date:	  20 August 2019
# Link:	  https://arxiv.org/abs/1906.08878
# ==========================================


if __name__ == '__main__':

    # Read arguments

    parser = argparse.ArgumentParser(description="Run BayesOpt Experiments")
    parser.add_argument('-f', '--func', help='Objective function',
                        default='dim10Rosenbrock',
                        type=str)  # Supported functions: 'func2C', 'func3C', 'dim10Rosenbrock',
    # 'linearmivabo', 'dim53Rosenbrock', 'dim53Ackley', 'dim238Rosenbrock'
    parser.add_argument('-mix', '--kernel_mix',
                        help='Mixture weight for production and summation kernel. Default = 0.0', default=0.5,
                        type=float)
    parser.add_argument('-n', '--max_itr', help='Max Optimisation iterations. Default = 100',
                        default=10, type=int)
    parser.add_argument('-tl', '--trials', help='Number of random trials. Default = 20',
                        default=1, type=int)
    parser.add_argument('-b', '--batch',
                        help='Batch size (>1 for batch CoCaBO and =1 for sequential CoCaBO). Default = 1',
                        default=1, type=int)

    args = parser.parse_args()
    print(f"Got arguments: \n{args}")
    obj_func = args.func
    kernel_mix = args.kernel_mix
    n_itrs = args.max_itr
    n_trials = args.trials
    batch = args.batch

    folder = os.path.join(os.path.curdir, 'data', 'syntheticFns', obj_func)
    if not os.path.isdir(folder):
        os.makedirs(folder)

    if obj_func == 'dim10Rosenbrock':
        ff = syntheticFunctions.dim10Rosenbrock
        d = 10  # Total number of variables
        lb = -2 * np.ones(d).astype(int)  # Lower bound
        ub = 2 * np.ones(d).astype(int)  # Upper bound
        num_int = 3  # number of integer variables
        lb[0:num_int] = 0
        ub[0:num_int] = num_int + 1
    elif obj_func == 'func3C':
        ff = syntheticFunctions.func3C
        d = 5  # Total number of variables
        lb = -1 * np.ones(d).astype(int)  # Lower bound for continuous variables
        ub = 1 * np.ones(d).astype(int)  # Upper bound for continuous variables
        num_int = 3  # number of integer variables
        lb[0:num_int] = 0
        ub[0] = 2
        ub[1] = 4
        ub[2] = 3
    elif obj_func == 'func2C':
        ff = syntheticFunctions.func2C
        d = 4  # Total number of variables
        lb = -1 * np.ones(d).astype(int)  # Lower bound for continuous variables
        ub = 1 * np.ones(d).astype(int)  # Upper bound for continuous variables
        num_int = 2  # number of integer variables
        lb[0:num_int] = 0
        ub[0] = 2
        ub[1] = 4
    elif obj_func == 'dim53Rosenbrock':
        ff = syntheticFunctions.dim53Rosenbrock
        d = 53  # Total number of variables
        lb = -2 * np.ones(d).astype(int)  # Lower bound
        ub = 2 * np.ones(d).astype(int)  # Upper bound
        num_int = 50  # number of integer variables
        lb[0:num_int] = 0
        ub[0:num_int] = 1
    elif obj_func == 'dim53Ackley':
        ff = syntheticFunctions.dim53Ackley
        d = 53  # Total number of variables
        lb = -1 * np.ones(d).astype(float)  # Lower bound
        ub = 1 * np.ones(d).astype(float)  # Upper bound
        num_int = 50  # number of integer variables
        lb[0:num_int] = 0
        ub[0:num_int] = 1
    elif obj_func == 'dim238Rosenbrock':
        ff = syntheticFunctions.dim238Rosenbrock
        d = 238  # Total number of variables
        lb = -2 * np.ones(d).astype(int)  # Lower bound
        ub = 2 * np.ones(d).astype(int)  # Upper bound
        num_int = 119  # number of integer variables
        lb[0:num_int] = 0
        ub[0:num_int] = 4
    else:
        raise NotImplementedError

    x0 = np.zeros(d)  # Initial guess
    x0[0:num_int] = np.round(
        np.random.rand(num_int) * (ub[0:num_int] - lb[0:num_int]) + lb[0:num_int])  # Random initial guess (integer)
    x0[num_int:d] = np.random.rand(d - num_int) * (ub[num_int:d] - lb[num_int:d]) + lb[
                                                                                    num_int:d]  # Random initial guess (continuous)

    rand_evals = 24  # Number of random iterations, same as initN above (24)
    max_evals = n_itrs + rand_evals  # Maximum number of MVRSM iterations, the first <rand_evals> are random


    ###########
    ## MVRSM ##
    ###########

    def obj_MVRSM(x):
        # print(x[0:num_int])
        h = np.copy(x[0:num_int]).astype(int)
        if obj_func == 'func3C' or obj_func == 'func2C':
            result = ff(h, x[num_int:])[0][0]
        elif obj_func == 'linearmivabo':
            result = ff(x)
        else:
            result = ff(h, x[num_int:])
        return result


    def run_MVRSM():
        solX, solY, model = MVRSM.MVRSM_minimize(obj_MVRSM, x0, lb, ub, num_int, max_evals, rand_evals)

        print("Solution found: ")
        print(f"X = {solX}")
        print(f"Y = {solY}")


    for i in range(n_trials):
        if obj_func == 'dim10Rosenbrock' or obj_func == 'dim53Rosenbrock' or obj_func == 'dim238Rosenbrock':
            print(f"Testing MVRSM on the {d}-dimensional Rosenbrock function with integer constraints.")
            print("The known global minimum is f(1,1,...,1)=0")
        else:
            print("Start MVRSM trials")
        run_MVRSM()


    ##############
    ## HyperOpt ##
    ##############

    # HyperOpt and RS objective
    def hyp_obj(x):
        f = obj_MVRSM(x)
        # print('Objective value: ', f)
        return {'loss': f, 'status': STATUS_OK}


    # Two algorithms used within HyperOpt framework (random search and TPE)
    algo = rand.suggest
    algo2 = partial(tpe.suggest, n_startup_jobs=rand_evals)

    # Define search space for HyperOpt
    var = [None] * d  # variable for hyperopt and random search
    for i in list(range(0, d)):
        if i < num_int:
            var[i] = hp.quniform('var_d' + str(i), lb[i], ub[i], 1)  # Integer variables
        else:
            var[i] = hp.uniform('var_c' + str(i), lb[i], ub[i])  # Continuous variables

    print("Start HyperOpt trials")
    for i in range(n_trials):
        current_time = time.time()  # time when starting the HO and RS algorithm

        trials_HO = Trials()
        time_start = time.time()  # Start timer
        hypOpt = fmin(hyp_obj, var, algo2, max_evals=max_evals, trials=trials_HO)  # Run HyperOpt
        total_time_HypOpt = time.time() - time_start  # End timer

        logfileHO = os.path.join(folder, 'log_HypOpt_' + str(current_time) + ".log")
        with open(logfileHO, 'a') as f:
            print(trials_HO.trials, file=f)  # Save log

        # write times per iteration to log
        logHOtimeperiteration = os.path.join(folder, 'HO_timeperiteration.txt')
        with open(logHOtimeperiteration, 'a') as f:
            for ii in range(0, max_evals):
                if ii == 0:
                    print(trials_HO.trials[ii]['book_time'].timestamp() - time_start, file=f)  # no 1 hour difference
                else:
                    print((trials_HO.trials[ii]['book_time'] - trials_HO.trials[ii - 1]['book_time']).total_seconds(),
                          file=f)

    ###################
    ## Random search ##
    ###################

    print("Start Random Search trials")
    for i in range(n_trials):
        current_time = time.time()  # time when starting the HO and RS algorithm
        trials_RS = Trials()

        time_start = time.time()
        RS = fmin(hyp_obj, var, algo, max_evals=max_evals, trials=trials_RS)
        total_time_RS = time.time() - time_start

        logfileRS = os.path.join(folder, 'log_RS_' + str(current_time) + ".log")
        with open(logfileRS, 'a') as f:
            print(trials_RS.trials, file=f)  # Save log

        # write times per iteration to log
        logRStimeperiteration = os.path.join(folder, 'RS_timeperiteration.txt')
        with open(logRStimeperiteration, 'a') as f:
            for i in range(0, max_evals):
                if i == 0:
                    print(trials_RS.trials[i]['book_time'].timestamp() - time_start,
                          file=f)  # no 1 hour difference
                else:
                    print((trials_RS.trials[i]['book_time'] - trials_RS.trials[i - 1]['book_time']).total_seconds(),
                          file=f)





