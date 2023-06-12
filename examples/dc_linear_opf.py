from GridCal.Engine import *
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

main_circuit = FileOpen(fname).open()

# main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                  apply_temperature=False,
                                                  branch_tolerance_mode=BranchImpedanceMode.Specified)

problem = OpfDc(numerical_circuit=numerical_circuit_)

print('Solving...')
status = problem.solve()

# print("Status:", status)

v = problem.get_voltage()
print('Angles\n', np.angle(v))

l = problem.get_loading()
print('Branch loading\n', l)

g = problem.get_generator_power()
print('Gen power\n', g)

pr = problem.get_shadow_prices()
print('Nodal prices \n', pr)