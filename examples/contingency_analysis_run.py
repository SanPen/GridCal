import os
from GridCalEngine.api import *
import GridCalEngine.basic_structures as bs

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE 5 Bus.xlsx')

main_circuit = FileOpen(fname).open()

branches = main_circuit.get_branches()

# manually generate the contingencies
for i, br in enumerate(branches):
    # add a contingency group
    group = ContingencyGroup(name="contingency {}".format(i+1))
    main_circuit.add_contingency_group(group)

    # add the branch contingency to the groups, only groups are failed at once
    con = Contingency(device_idtag=br.idtag, name=br.name, group=group)
    main_circuit.add_contingency(con)

# add a special contingency
group = ContingencyGroup(name="Special contingency")
main_circuit.add_contingency_group(group)
main_circuit.add_contingency(Contingency(device_idtag=branches[3].idtag, name=branches[3].name, group=group))
main_circuit.add_contingency(Contingency(device_idtag=branches[5].idtag, name=branches[5].name, group=group))

pf_options = PowerFlowOptions(solver_type=SolverType.NR)

# declare the contingency options
options_ = ContingencyAnalysisOptions(distributed_slack=True,
                                      correct_values=True,
                                      use_provided_flows=False,
                                      Pf=None,
                                      pf_results=None,
                                      engine=bs.ContingencyEngine.PowerFlow,
                                      pf_options=pf_options)

linear_multiple_contingencies = LinearMultiContingencies(grid=main_circuit)

simulation = ContingencyAnalysisDriver(grid=main_circuit,
                                       options=options_,
                                       linear_multiple_contingencies=linear_multiple_contingencies)

simulation.run()

# print results
df = simulation.results.mdl(ResultTypes.BranchActivePowerFrom).to_df()
print(df)
