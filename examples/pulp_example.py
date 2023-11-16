import pulp as pl

solver_list = pl.listSolvers(onlyAvailable=True)

print(solver_list)
