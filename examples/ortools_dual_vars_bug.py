import os
from ortools.linear_solver.python import model_builder

path = os.path.dirname(__file__)
mps_path = "Lynn 5 Bus pv (OPF).mps"
model = model_builder.ModelBuilder()
model.import_from_mps_file(mps_path)
solver = model_builder.ModelSolver('SCIP')
solver.solve(model)

print(model.name)
print(solver.objective_value)
for cts in model.get_linear_constraints():
    print(cts.name + ' ->', solver.dual_value(cts))

print("End")