from ortools.linear_solver import pywraplp

solver = pywraplp.Solver.CreateSolver('GUROBI')

solver = pywraplp.Solver.CreateSolver('CPLEX')
