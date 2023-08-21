import time
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.IO.gridcal.sqlite_interface import save_data_frames_to_sqlite, open_data_frames_from_sqlite
from GridCal.Engine.IO.gridcal.pack_unpack import create_data_frames, data_frames_to_circuit

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'

a = time.time()
circuit_ = FileOpen(fname).open()
print('native based open:', time.time() - a)

print('Saving .sqlite ...')
dfs = create_data_frames(circuit=circuit_)
save_data_frames_to_sqlite(dfs, file_path=circuit_.name + '.sqlite')

a = time.time()
data = open_data_frames_from_sqlite(circuit_.name + '.sqlite')
circuit2 = data_frames_to_circuit(data)
print('sql based open:', time.time() - a)