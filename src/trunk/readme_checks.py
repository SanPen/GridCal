import os
import GridCalEngine as gce
# from GridCalEngine import Contingency, SolverType, ResultTypes  # Import Contingency explicitly


folder = os.path.join('..','..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE 5 Bus.xlsx')

main_circuit = gce.open_file(fname)

branches = main_circuit.get_branches()

# manually generate the contingencies
for i, br in enumerate(branches):
    # add a contingency group
    group = gce.ContingencyGroup(name="contingency {}".format(i + 1))
    main_circuit.add_contingency_group(group)

    # add the branch contingency to the groups, only groups are failed at once
    # con = Contingency(device_idtag=br.idtag, name=br.name, group=group)  # Use imported Contingency
    con = gce.Contingency(device=br, name=br.name, group=group)
    main_circuit.add_contingency(con)

# add a special contingency
group = gce.ContingencyGroup(name="Special contingency")
main_circuit.add_contingency_group(group)
main_circuit.add_contingency(gce.Contingency(device=branches[3], name=branches[3].name, group=group))
main_circuit.add_contingency(gce.Contingency(device=branches[5], name=branches[5].name, group=group))

pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)

# declare the contingency options
options_ = gce.ContingencyAnalysisOptions(use_provided_flows=False,
                                          Pf=None,
                                          contingency_method=gce.ContingencyMethod.PowerFlow,
                                          # if no power flow options are provided
                                          # if no power flow options are provided
                                          # a linear power flow is used
                                          pf_options=pf_options)

# Get all the defined contingency groups from the circuit
contingency_groups = main_circuit.get_contingency_groups()

# Pass the list of contingency groups as required
linear_multiple_contingencies = gce.LinearMultiContingencies(grid=main_circuit,
                                                             contingency_groups_used=contingency_groups)

# linear_multiple_contingencies = gce.LinearMultiContingencies(grid=main_circuit)

simulation = gce.ContingencyAnalysisDriver(grid=main_circuit,
                                           options=options_,
                                           linear_multiple_contingencies=linear_multiple_contingencies)

simulation.run()

# print results
df = simulation.results.mdl(gce.ResultTypes.BranchActivePowerFrom).to_df()
print("Contingency flows:\n", df)