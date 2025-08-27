import numpy as np
import pygslv as pg
# import VeraGridEngine.Utils.ThirdParty.pulp as pulp
import pulp
import datetime

from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder import BoundedLinearExpression as LpCstBounded
from ortools.linear_solver.python.model_builder import LinearConstraint as LpCst
from ortools.linear_solver.python.model_builder import LinearExpr as LpExp
from ortools.linear_solver.python.model_builder import Variable as LpVar


def gslv_exaple(n=10000):
    print("GSLV", pg.get_version())
    t1 = datetime.datetime.now()

    m = pg.LpModel()

    x = np.empty(n, dtype=object)
    for i in range(n):
        x[i] = m.add_var("x", 0, 1e20)

    for i in range(2 * n):
        nn = np.random.randint(low=2, high=20)

        coeff = np.random.rand(nn)
        pos = np.random.randint(low=0, high=n, size=nn)
        cst = sum(coeff[k] * x[pos[k]] for k in range(nn)) >= 0.0
        m.add_cst(cst)

    m.minimize(sum(x))

    t2 = datetime.datetime.now()

    dt = t2 - t1
    print(f"GSLV done! {dt.total_seconds()} seconds")


def pulp_exaple(n=10000):
    print("PuLP", pulp.__version__)
    t1 = datetime.datetime.now()

    m = pulp.LpProblem("test", pulp.LpMinimize)

    x = np.empty(n, dtype=object)
    for i in range(n):
        x[i] = pulp.LpVariable("var", 0, 1e20, pulp.LpInteger)
        m.addVariable(x[i])

    for i in range(2 * n):
        nn = np.random.randint(low=2, high=20)

        coeff = np.random.rand(nn)
        pos = np.random.randint(low=0, high=n, size=nn)
        cst = sum(coeff[k] * x[pos[k]] for k in range(nn)) >= 0.0
        m.addConstraint(cst)

    m.setObjective(sum(x))

    t2 = datetime.datetime.now()

    dt = t2 - t1
    print(f"PuLP done! {dt.total_seconds()} seconds")


def ortools_example(n=10000):
    print("OrTools")
    t1 = datetime.datetime.now()

    m = model_builder.Model()

    x = np.empty(n, dtype=object)
    for i in range(n):
        x[i] = m.new_var(name="var", lb=0, ub=1e20, is_integer=True)

    for i in range(2 * n):
        nn = np.random.randint(low=2, high=20)

        coeff = np.random.rand(nn)
        pos = np.random.randint(low=0, high=n, size=nn)
        cst = sum(coeff[k] * x[pos[k]] for k in range(nn)) >= 0.0
        m.add(cst)

    m.minimize(sum(x))

    t2 = datetime.datetime.now()

    dt = t2 - t1
    print(f"OrTools done! {dt.total_seconds()} seconds")



if __name__ == "__main__":
    gslv_exaple(n=100000)
    ortools_example(n=100000)
    pulp_exaple(n=100000)
