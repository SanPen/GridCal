import VeraGridEngine as gce

grid = gce.open_file("/home/santi/Descargas/IEEE 14 Contingencies.veragrid")

# ----------------------------------------------------------------------------------------------------------------------
# Generate contingencies
# ----------------------------------------------------------------------------------------------------------------------
contingency_groups = list(grid.get_contingency_groups())
for contin in contingency_groups:
    grid.delete_contingency_group(contin)

branches = grid.get_branches()
generators = grid.get_generators()

for i, br in enumerate(branches):
    group_name = "contingency branch {}-{}".format(
        br.bus_from.name.lower(),
        br.bus_to.name.lower()
    )
    group = gce.ContingencyGroup(name=group_name)
    print(f"  [{i + 1}/{len(branches)}] Added group: {group.name}")
    grid.add_contingency_group(group)

    con = gce.Contingency(device=br, name=br.name, group=group)
    grid.add_contingency(con)

for i, gen in enumerate(generators):
    group_name = "contingency generator {}".format(gen.name.lower())
    group = gce.ContingencyGroup(name=group_name)
    print(f"  [{i + 1}/{len(generators)}] Added group: {group.name}")
    grid.add_contingency_group(group)

    con = gce.Contingency(device=gen, name=gen.name, group=group)
    grid.add_contingency(con)

# ----------------------------------------------------------------------------------------------------------------------
# Run nonlinear PF
# ----------------------------------------------------------------------------------------------------------------------
nl_power_flow = gce.PowerFlowDriver(
    grid=grid,
    options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
)
nl_power_flow.run()

# ----------------------------------------------------------------------------------------------------------------------
# Run Linear PF
# ----------------------------------------------------------------------------------------------------------------------
lin_power_flow = gce.PowerFlowDriver(
    grid=grid,
    options=gce.PowerFlowOptions(solver_type=gce.SolverType.Linear)
)
lin_power_flow.run()

# ----------------------------------------------------------------------------------------------------------------------
# Run nonlinear contingencies
# ----------------------------------------------------------------------------------------------------------------------
pf_contingencies = gce.ContingencyAnalysisDriver(
    grid=grid,
    options=gce.ContingencyAnalysisOptions(
        contingency_method=gce.ContingencyMethod.PowerFlow,
        contingency_groups=grid.contingency_groups,
        pf_options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ),
)
pf_contingencies.run()

# ----------------------------------------------------------------------------------------------------------------------
# Run linear contingencies
# ----------------------------------------------------------------------------------------------------------------------
lin_contingencies = gce.ContingencyAnalysisDriver(
    grid=grid,
    options=gce.ContingencyAnalysisOptions(
        contingency_method=gce.ContingencyMethod.Linear,
        contingency_groups=grid.contingency_groups
    )
)
lin_contingencies.run()

print("\nScript completed successfully.")
