# IDONE

IDONE uses a piece-wise linear surrogate model for optimization of expensive cost functions with integer variables. The method is described in https://arxiv.org/abs/1911.08817.

`IDONE_minimize(f, x0, lb, ub, max_evals)` solves the minimization problem

**min** *f(x)*

**st.** *lb<=x<=ub, x is integer*

where `f` is the objective function, `x0` the initial guess,
`lb` and `ub` are the bounds (assumed integer), 
and `max_evals` is the maximum number of objective evaluations.

It is the discrete version of the [DONE algorithm](https://bitbucket.org/csi-dcsc/donecpp/src/master/).

This version runs in Python 3.7.

Dependencies:

* Numpy (tested on version 1.17)
* Scipy (tested on version 1.3)

A demo file to run IDONE on a higher-dimensional Rosenbrock function has been included. To run it, run `demo_Rosenbrock.py`.

Please contact l.bliek@tudelft.nl if you have any questions.




